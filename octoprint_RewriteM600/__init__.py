# coding=utf-8
from __future__ import absolute_import

from octoprint.plugin import StartupPlugin, AssetPlugin
from octoprint.plugin import TemplatePlugin, SettingsPlugin
from octoprint.util.comm import PositionRecord


class Rewritem600Plugin(StartupPlugin, AssetPlugin, TemplatePlugin, SettingsPlugin):
    def __init__(self):
        self.pause_position = PositionRecord()
        self.changing_filament = False

    def on_after_startup(self):
        self._logger.info("Hello World!")

    def rewrite_m600(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        if gcode and gcode == "M600":
            self._logger.info("M600 received")
            dwargs = dict(type="popup", msg="Change filament and resume")
            self._plugin_manager.send_plugin_message(self._identifier, dwargs)

            comm_instance.setPause(True)
            self.changing_filament = True

            cmd = [("M117 Filament Change",)]       # LCD message

        return cmd

    def m600_hook(self, comm_instance, script_type, script_name, *args, **kwargs):
        self._logger.info("m600_hook %s: %s" % (script_type, script_name))
        #
        if script_type == "gcode" and script_name == "afterPrintPaused" and self.changing_filament:
            self.pause_position.copy_from(comm_instance.pause_position)
            get_bool = self._settings.get_boolean
            get = self._settings.get

            self._logger.info(
                "AfterPause: pause_position X%f Z%f" % (self.pause_position.x,
                                                        self.pause_position.z)
            )
            postix = None
            prefix = ["G91",           # relative XYZE
                      "M83",           # relative E
                      "G1 Z%s E-5 F3000" % get(["zDistance"]),
                      "M82",           # absolute E
                      "G90",           # absolute XYZE
                      "G0 X%s Y%s F3000" % (get(["toolChangeX"]),  # go to filament change location
                                            get(["toolChangeY"])
                                            ),
                      "G91",           # relative XYZE
                      "M83",           # relative E
                      "G1 E-%s F200" % get(["retractDistance"]),
                      "M82",           # absolute E
                      "G90"            # absolute XYZE
                      ]
            if get_bool(["DisableSteppers"]):
                prefix.append("M84" +
                              " X" if get(["DisableX"]) else "" +
                              " Y" if get(["DisableY"]) else "" +
                              " Z" if get(["DisableZ"]) else "" +
                              " E" if get(["DisableE"]) else ""
                              )

            if get_bool(["PostixEnableSteppers"]) and get_bool(["DisableSteppers"]):
                postix = ["M17",
                          " X" if not get(["DisableX"]) else "",
                          " Y" if not get(["DisableY"]) else "",
                          " Z" if not get(["DisableZ"]) else "",
                          " E" if not get(["DisableE"]) else ""
                          ]

            self._logger.info("prefix: " + ", ".join(prefix))
            if postix:
                self._logger.info("postix: " + ", ".join(postix))

            return prefix, postix
        #
        if script_type == "gcode" and script_name == "beforePrintResumed" and self.changing_filament:
            self.changing_filament = False
            pause_position = (self.pause_position.x, self.pause_position.y,
                              self.pause_position.z, self.pause_position.e)
            self._logger.info(
                "BeforeResume: pause_position X%f Y%f Z%f E%f" % pause_position)
            postix = None
            prefix = []
            if self._settings.get_boolean(["DisableSteppers"]):
                prefix.append("M17")      # resume all steppers
        
            prefix.append("G90")          # Absolute Positioning
            prefix.append("M82")          # Absolute E
            prefix.append("G92 E%f" % pause_position[3])  # Set E
            prefix.append("G0 X%f Y%f Z%f F4500" % pause_position[0:3])
            if self.pause_position.f:
                prefix.append("G0 F%f" % self.pause_position.f)
            return prefix, postix

    def get_settings_defaults(self):
        return dict(zDistance=10,
                    toolChangeX=-10,
                    toolChangeY=-10,
                    retractDistance=55,
                    DisableSteppers=False,
                    DisableX=False,
                    DisableY=False,
                    DisableZ=False,
                    DisableE=False,
                    PostixEnableSteppers=False)

    def get_template_configs(self):
        return [dict(type="navbar", custom_bindings=False),
                dict(type="settings", custom_bindings=False)]

    def get_assets(self):
        """AssetPlugin mixin"""
        return dict(js=["js/RewriteM600.js"],
                    css=["css/RewriteM600.css"],
                    less=["less/RewriteM600.less"])

    def get_update_information(self):
        """ Software Update hook.
        
        Define the configuration for your plugin to use with the Software Update 
        """
        m600_dict = dict(displayName="Rewritem600 Plugin Quim",
                         displayVersion=self._plugin_version,
                         # version check: github repository
                         type="github_release",
                         user="joaquinabian",
                         repo="RewriteM600",
                         current=self._plugin_version,
                         # update method: pip
                         pip="https://github.com/jepler/RewriteM600/archive/{target_version}.zip")
        
        return dict(RewriteM600=m600_dict)


__plugin_name__ = "Filament Change - M600 Rewriter Quim"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = Rewritem600Plugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.rewrite_m600,
        "octoprint.comm.protocol.scripts":  __plugin_implementation__.m600_hook,
    }
