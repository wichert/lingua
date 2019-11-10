from setuptools import setup, find_packages
import sys

version = '4.14'

install_requires = [
    'setuptools',
    'polib',
    'click',
    'ordereddict;python_version<"3.0"',
    'mock;python_version<"3.3"',
]

tests_require = [
    'pytest',
]


setup(name='lingua',
      version=version,
      description='Translation toolset',
      long_description=open('README.rst').read() + '\n' +
              open('changes.rst').read(),
      classifiers=[
          'Intended Audience :: Developers',
          'License :: DFSG approved',
          'License :: OSI Approved :: BSD License',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ],
      keywords='translation po gettext Babel',
      author='Wichert Akkerman',
      author_email='wichert@wiggy.net',
      url='https://github.com/wichert/lingua',
      license='BSD',
      packages=find_packages('src'),
      package_dir={'': 'src'},
      include_package_data=True,
      zip_safe=True,
      install_requires=install_requires,
      tests_require=tests_require,
      extras_require={
          'tests': tests_require,
          'chameleonextractor': ['Chameleon'],
      },
      entry_points='''
      [console_scripts]
      polint = lingua.polint:main
      pot-create = lingua.extract:main

      [lingua.extractors]
      python = lingua.extractors.python:PythonExtractor
      chameleon = lingua.extractors.xml:ChameleonExtractor [chameleonextractor]
      xml = lingua.extractors.xml:ChameleonExtractor [chameleonextractor]
      zope = lingua.extractors.xml:ZopeExtractor [chameleonextractor]
      zcml = lingua.extractors.zcml:ZCMLExtractor
      '''
      )
