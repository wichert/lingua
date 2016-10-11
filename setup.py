from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys

version = '4.12'

install_requires = [
    'setuptools',
    'polib',
    'Chameleon',
]

tests_require = [
    'pytest',
]

if sys.version_info < (2, 7):
    install_requires.append('argparse')
    install_requires.append('ordereddict')

if (3, 0) < sys.version_info < (3, 3):
    tests_require.append('mock')


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = ['tests']
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


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
      extras_require={'tests': tests_require},
      cmdclass={'test': PyTest},
      entry_points='''
      [console_scripts]
      polint = lingua.polint:main
      pot-create = lingua.extract:main

      [lingua.extractors]
      python = lingua.extractors.python:PythonExtractor
      chameleon = lingua.extractors.xml:ChameleonExtractor
      xml = lingua.extractors.xml:ChameleonExtractor
      zope = lingua.extractors.xml:ZopeExtractor
      zcml = lingua.extractors.zcml:ZCMLExtractor
      '''
      )
