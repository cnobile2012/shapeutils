from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='shputils',
      version=version,
      description="Read shape files.",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='shapefile geo maps',
      author='Carl J. Nobile',
      author_email='carl.nobile@gmail.com',
      url='www.tetrasys-design.net',
      license='',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=True,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
