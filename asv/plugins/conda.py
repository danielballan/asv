# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os
import shutil
import tempfile

import six

from .. import environment
from ..console import log
from .. import util


class Conda(environment.Environment):
    """
    Manage an environment using conda.

    Dependencies are installed using ``conda``.  The benchmarked
    project is installed using ``pip`` (since ``conda`` doesn't have a
    method to install from an arbitrary ``setup.py``).
    """
    def __init__(self, env_dir, python, requirements):
        """
        Parameters
        ----------
        env_dir : str
            Root path in which to cache environments on disk.

        python : str
            Version of Python.  Must be of the form "MAJOR.MINOR".

        requirements : dict
            Dictionary mapping a PyPI package name to a version
            identifier string.
        """
        self._env_dir = env_dir
        self._python = python
        self._requirements = requirements
        self._path = os.path.join(
            self._env_dir, self.name)

        self._is_setup = False
        self._requirements_installed = False

    @classmethod
    def matches(self, python):
        try:
            conda = util.which('conda')
        except IOError:
            return False
        else:
            # This directory never gets created, since we're just
            # doing a dry run below.  All it needs to be is something
            # that doesn't already exist.
            path = os.path.join(tempfile.gettempdir(), 'check')
            # Check that the version number is valid
            try:
                util.check_call([
                    conda,
                    'create',
                    '--yes',
                    '-p',
                    path,
                    'python={0}'.format(python),
                    '--dry-run'])
            except util.ProcessError:
                return False
            else:
                return True

    @classmethod
    def get_environments(cls, conf, python):
        for configuration in environment.iter_configuration_matrix(conf.matrix):
            yield cls(conf.env_dir, python, configuration)

    def setup(self):
        if self._is_setup:
            return

        if not os.path.exists(self._env_dir):
            os.makedirs(self._env_dir)

        # We start with a clean conda environment everytime, since
        # they are so quick to create.
        if os.path.exists(self._path):
            shutil.rmtree(self._path)

        conda = util.which('conda')

        log.info("Creating conda environment for {0}".format(self.name))
        try:
            util.check_call([
                conda,
                'create',
                '--yes',
                '-p',
                self._path,
                'python={0}'.format(self._python), 'pip'])
        except util.ProcessError:
            log.error("Failure creating conda environment for {0}".format(
                self.name))
            if os.path.exists(self._path):
                shutil.rmtree(self._path)
            raise

        self._is_setup = True

    def install_requirements(self):
        if self._requirements_installed:
            return

        self.setup()

        for key, val in six.iteritems(self._requirements):
            if val is not None:
                self.upgrade("{0}={1}".format(key, val))
            else:
                self.upgrade(key)

        self._requirements_installed = True

    def _run_executable(self, executable, args, **kwargs):
        return util.check_output([
            os.path.join(self._path, 'bin', executable)] + args, **kwargs)

    def install(self, package, editable=False):
        rel = os.path.relpath(package, os.getcwd())
        log.info("Installing {0} into {1}".format(rel, self.name))
        args = ['install']
        if editable:
            args.append('-e')
        args.append(package)
        self._run_executable('pip', args)

    def upgrade(self, package):
        log.info("Upgrading {0} in {1}".format(package, self.name))
        self._run_executable(
            'conda',
            ['install', '-p', self._path, '--yes', package])

    def uninstall(self, package):
        log.info("Uninstalling {0} from {1}".format(package, self.name))
        self._run_executable('pip', ['uninstall', '-y', package], error=False)

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        self.install_requirements()
        return self._run_executable('python', args, **kwargs)
