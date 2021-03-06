#!/usr/bin/python -tt
# coding:utf-8


from setuptools import setup


if __name__ == '__main__':
    setup(
        name='gocdpb',
        version='7.2',
        description='Configure GoCD pipeline from the commandline.',
        long_description=(
            'The Go CD Pipeline Builder is designed to have the same '
            'function in the GoCD eco system, as the Jenkins Job Builder '
            'has in the Jenkins eco system. '
            'Given a (git) repository and appropriate configuration, '
            'it should be able to add a suitable pipeline to a Go-server. '
            'The current version does not trigger on git events. '
            'It is simply a command line driven tool.'
        ),
        author='Magnus Lyckå',
        author_email='magnus@thinkware.se',
        license='MIT',
        url='https://github.com/magnus-lycka/gocd-pipeline-builder',
        classifiers=[
            "Programming Language :: Python :: 2.7",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "Topic :: Software Development :: Build Tools",
            "Environment :: Console",
        ],
        keywords='continuous deployment integration build automation gocd',
        package_dir={'gocdpb': 'src/main'},
        packages=['gocdpb'],
        install_requires=['jinja2', 'requests', 'PyYAML'],
        entry_points={
            'console_scripts': [
                'gocdpb=gocdpb.gocdpb:main',
                'gocdrepos=gocdpb.gocdpb:repos',
                'gocdtagrepos=gocdpb.tagrepos:main',
            ]
        }
    )
