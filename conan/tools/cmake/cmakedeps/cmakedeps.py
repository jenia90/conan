import os

from conan.tools.cmake.cmakedeps.templates.config import ConfigTemplate
from conan.tools.cmake.cmakedeps.templates.config_version import ConfigVersionTemplate
from conan.tools.cmake.cmakedeps.templates.macros import MacrosTemplate
from conan.tools.cmake.cmakedeps.templates.target_configuration import TargetConfigurationTemplate
from conan.tools.cmake.cmakedeps.templates.target_data import ConfigDataTemplate
from conan.tools.cmake.cmakedeps.templates.targets import TargetsTemplate
from conans.errors import ConanException
from conans.util.files import save


class CMakeDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.arch = self._conanfile.settings.get_safe("arch")
        self.configuration = str(self._conanfile.settings.build_type)

        self.configurations = [v for v in conanfile.settings.build_type.values_range if v != "None"]
        # Activate the build config files for the specified libraries
        self.build_context_activated = []
        # By default, the build modules are generated for host context only
        self.build_context_build_modules = []
        # If specified, the files/targets/variables for the build context will be renamed appending
        # a suffix. It is necessary in case of same require and build_require and will cause an error
        self.build_context_suffix = {}

    def generate(self):
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    @property
    def content(self):
        macros = MacrosTemplate()
        ret = {macros.filename: macros.render()}

        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.direct_build

        # Check if the same package is at host and build and the same time
        activated_br = {r.ref.name for r in build_req.values()
                        if r.ref.name in self.build_context_activated}
        common_names = {r.ref.name for r in host_req.values()}.intersection(activated_br)
        for common_name in common_names:
            suffix = self.build_context_suffix.get(common_name)
            if not suffix:
                raise ConanException("The package '{}' exists both as 'require' and as "
                                     "'build require'. You need to specify a suffix using the "
                                     "'build_context_suffix' attribute at the CMakeDeps "
                                     "generator.".format(common_name))

        # Iterate all the transitive requires
        for require, dep in list(host_req.items()) + list(build_req.items()):
            # Require is not used at the moment, but its information could be used,
            # and will be used in Conan 2.0
            # Filter the build_requires not activated with cmakedeps.build_context_activated
            if dep.is_build_context and dep.ref.name not in self.build_context_activated:
                continue

            if dep.new_cpp_info.get_property("skip_deps_file", "CMakeDeps"):
                # Skip the generation of config files for this node, it will be located externally
                continue

            config_version = ConfigVersionTemplate(self, require, dep)
            ret[config_version.filename] = config_version.render()

            data_target = ConfigDataTemplate(self, require, dep)
            ret[data_target.filename] = data_target.render()

            target_configuration = TargetConfigurationTemplate(self, require, dep)
            ret[target_configuration.filename] = target_configuration.render()

            targets = TargetsTemplate(self, require, dep)
            ret[targets.filename] = targets.render()

            config = ConfigTemplate(self, require, dep)
            # Check if the XXConfig.cmake exists to keep the first generated configuration
            # to only include the build_modules from the first conan install. The rest of the
            # file is common for the different configurations.
            if not os.path.exists(config.filename):
                ret[config.filename] = config.render()
        return ret
