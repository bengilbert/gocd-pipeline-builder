import copy
import sys
import json
from collections import OrderedDict
import yaml
from jinja2 import Template
from xml.etree import ElementTree


def get_settings(settings_file):
    """
    Factory function returning a settings object from a Yaml och Json file.

    A Json file passed to the factory should have the following structure:
    {
        "environment": "green",
        "pipelines": [ <pipeline> ... ]
    }

    Each <pipeline> should conform to the spec here:
    https://api.go.cd/current/#create-a-pipeline

    If a Yaml file is passed to the factory, it will return a settings
    object created from a Jinja template and parameters in the Yaml file.
    The end result should be as for Json files as described above.

    :param settings_file: a Yaml or Json file.
    :return: A JsonSettings instance (or instance of subclass)
    """
    if settings_file.name.endswith('.json'):
        return JsonSettings(settings_file)
    else:
        return YamlSettings(settings_file)


class JsonSettings(object):
    """
    See get_settings() factory function.
    """
    def __init__(self, settings_file):
        self.list = None
        self.load_structure(settings_file)

    def server_operations(self, go):
        for operation in self.list:
            name = None
            if "create-a-pipeline" in operation:
                go.create_a_pipeline(operation["create-a-pipeline"])
                name = operation["create-a-pipeline"]["pipeline"]["name"]
            if name and "environment" in operation:
                go.init()
                self.update_environment(go.tree)
                if go.need_to_upload_config:
                    go.upload_config()
            if "add-downstream-dependencies" in operation:
                dependency_updates = operation["add-downstream-dependencies"]
                for dependency_update in dependency_updates:
                    name = dependency_update["name"]
                    etag, pipeline = go.get_pipeline_config(name)
                    # If this pipeline uses a template, we need to use that!!!
                    self.add_downstream_dependencies(pipeline, dependency_update)
                    go.edit_pipeline_config(name, etag, pipeline)
            # TODO POST /go/api/pipelines/:pipeline_name/unpause

    @classmethod
    def add_downstream_dependencies(cls, pipeline, update):
        if "material" in update:
            pipeline["materials"].append(update["material"])
        if "task" in update:
            if "stages" in pipeline:
                job = cls.get_job(pipeline, update)
                job["tasks"].insert(0, update["task"])
            else:
                sys.stderr.write("Adding tasks to template not supported!\n")

    @staticmethod
    def get_job(pipeline, update):
        if "stage" in update:
            for stage in pipeline["stages"]:
                if stage["name"] == update["stage"]:
                    break
        else:
            stage = pipeline["stages"][0]
        if "job" in update:
            for job in stage["jobs"]:
                if job["name"] == update["job"]:
                    break
        else:
            job = stage["jobs"][0]
        return job

    def load_structure(self, settings_file=None, settings_string=None):
        if settings_file:
            settings_string = settings_file.read()
        try:
            structure = json.loads(settings_string, object_pairs_hook=OrderedDict)
        except ValueError:
            print settings_string
            raise
        self.list = structure

    def update_environment(self, configuration):
        """
        If the setting names an environment, the pipelines in the
        setting, should be assigned to that environment in the cruise-config.
        """
        conf_environments = configuration.find('environments')
        if conf_environments is None:
            print "No environments section in configuration."
            return
        for operation in self.list:
            op_env_name = operation.get('environment')
            if not op_env_name:
                continue
            for conf_environment in conf_environments.findall('environment'):
                if conf_environment.get('name') == op_env_name:
                    data = operation.get('create-a-pipeline')
                    if data:
                        pipeline = data.get('pipeline')
                        name = pipeline.get('name')
                        self._set_pipeline_in_environment(name, conf_environment)
                    break

    @staticmethod
    def _set_pipeline_in_environment(name, conf_environment):
        conf_pipelines = conf_environment.find('pipelines')
        if conf_pipelines is None:
            conf_pipelines = ElementTree.SubElement(
                conf_environment, 'pipelines')
        # TODO: Check if already there?
        conf_pipeline = ElementTree.SubElement(conf_pipelines, 'pipeline')
        conf_pipeline.set('name', name)


class YamlSettings(JsonSettings):
    """
    See get_settings() factory function.
    """
    def load_structure(self, settings_file):
        """
        Find the Json template and parameter in the Yaml file,
        render the template, and pass it to the super class.
        """
        structure = yaml.load(settings_file)
        template = Template(open(structure['path']).read())
        settings = template.render(structure['parameters'])
        super(YamlSettings, self).load_structure(settings_string=settings)


class CruiseTree(ElementTree.ElementTree):
    """
    A thin layer on top of the cruise-config.xml used by the Go server.
    """
    @classmethod
    def fromstring(cls, text):
        return cls(ElementTree.fromstring(text))

    def tostring(self):
        self.indent(self.getroot())
        return ElementTree.tostring(self.getroot())

    def config_subset_tostring(self):
        """
        See GoProxy.set_test_settings_xml()
        """
        root = copy.deepcopy(self).getroot()
        for child in list(root):
            if child.tag not in ('pipelines', 'templates', 'environments'):
                root.remove(child)
        self.indent(root)
        return ElementTree.tostring(root)

    @classmethod
    def indent(cls, elem, level=0):
        """
        Fredrik Lundh's standard recipe.
        (Why isn't this in xml.etree???)
        """
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                cls.indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def set_test_settings_xml(self, test_settings_xml):
        """
        Replace parts of the Go server config for test purposes

        The main sections in the config are:
        - server
        - repositories
        - pipelines * N
        - templates
        - environments
        - agents
        We want to replace the sections pipelines*, templates and environments.
        Let server and agents stay as usual.
        We've never used repositories so far.
        """
        root = self.getroot()

        self.drop_sections_to_be_replaced(root)

        test_settings = CruiseTree().parse(test_settings_xml)

        ix = self.place_for_test_settings(root)

        for element_type in ('environments', 'templates', 'pipelines'):
            for elem in reversed(test_settings.findall(element_type)):
                root.insert(ix, elem)

    def drop_sections_to_be_replaced(self, root):
        for tag in ('pipelines', 'templates', 'environments'):
            for element_to_drop in self.findall(tag):
                root.remove(element_to_drop)

    @staticmethod
    def place_for_test_settings(root):
        ix = 0  # Silence lint about using ix after the loop. root != []
        for ix, element in enumerate(list(root)):
            if element.tag == 'agents':
                break
        return ix