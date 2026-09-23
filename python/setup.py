from setuptools import setup
from wheel.bdist_wheel import bdist_wheel
import os


class PlatformWheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure = False
        if os.environ.get("MARIAMEM_WHEEL_PLATFORM"):
            self.plat_name = os.environ["MARIAMEM_WHEEL_PLATFORM"]
            self.plat_name_supplied = True

    def get_tag(self):
        _, _, platform = super().get_tag()
        return "py3", "none", platform


setup(cmdclass={"bdist_wheel": PlatformWheel})
