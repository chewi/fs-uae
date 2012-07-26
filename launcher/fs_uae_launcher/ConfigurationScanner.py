from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import sys
import time
import traceback
import xml.etree.ElementTree
from xml.etree.cElementTree import ElementTree
from .Database import Database
from .Settings import Settings
from .I18N import _, ngettext

class ConfigurationScanner:

    def __init__(self, paths, on_status=None, stop_check=None):
        self.paths = paths
        self.on_status = on_status
        self._stop_check = stop_check
        self.scan_count = 0
        self.scan_version = int(time.time() * 100)

    def stop_check(self):
        if self._stop_check:
            return self._stop_check()

    def set_status(self, title, status):
        if self.on_status:
            self.on_status((title, status))

    def scan_fs_uae_files(self, database):
        configurations = database.get_files(ext=".fs-uae")
        for c in configurations:
            if self.stop_check():
                break
            name = os.path.basename(c["path"])
            name = name[:-7]
            search = name.lower()
            path = c["path"]
            name, ext = os.path.splitext(os.path.basename(path))
            name = self.create_configuration_name(name)
            database.add_configuration(path=path, uuid="", name=name,
                    scan=self.scan_version, search=search)

    def scan_builtin_configs(self, database):
        from .BuiltinConfigs import builtin_configs
        for name, data in builtin_configs.iteritems():
            if self.stop_check():
                break
            search = name.lower()
            name = self.create_configuration_name(name)
            database.add_configuration(data=data, name=name,
                    scan=self.scan_version, search=search)

    def scan(self):
        self.set_status(_("Scanning configurations"), _("Please wait..."))
        database = Database()

        self.scan_fs_uae_files(database)
        self.scan_configurations(database)
        self.scan_builtin_configs(database)

        if self.stop_check():
            # aborted
            #database.rollback()
            return

        #database.remove_unscanned_configurations(self.scan_version)
        print("remove unscanned games")
        self.set_status(_("Scanning configurations"), _("Purging old entries..."))
        database.remove_unscanned_games(self.scan_version)
        print("remove unscanned configurations")
        database.remove_unscanned_configurations(self.scan_version)
        self.set_status(_("Scanning configurations"), _("Commiting data..."))
        database.commit()

    def scan_configurations(self, database):
        for dir in self.paths:
            if self.stop_check():
                return
            self.scan_dir(database, dir)

    def scan_dir(self, database, dir):
        #print("scan dir for configurations:", dir)
        if not isinstance(dir, unicode):
            dir = dir.decode(sys.getfilesystemencoding())
        if not os.path.exists(dir):
            print("does not exist")
            return
        for name in os.listdir(dir):
            if self.stop_check():
                return
            path = os.path.join(dir, name)
            if os.path.isdir(path):
                self.scan_dir(database, path)
                continue
            dummy, ext = os.path.splitext(path)
            ext = ext.lower()
            #if ext not in self.extensions:
            #    continue
            if ext != ".xml":
                continue

            self.scan_count += 1
            self.set_status(
                    _("Scanning configurations ({count} scanned)").format(
                    count=self.scan_count), name)

            print("scan", name)
            result = None
            try:
                tree = ElementTree()
                tree.parse(path)
                root = tree.getroot()
                if root.tag == "config":
                    result = self.scan_configuration(database, tree)
                elif root.tag == "game":
                    self.scan_game(database, tree, path)
            except Exception:
                traceback.print_exc()
            if result is not None:
                if "name" in result:
                    name = result["name"]
                else:
                    name, ext = os.path.splitext(name)
                print("found", name)
                search = name.lower()
                #name = self.create_configuration_name_from_path(path)
                name = self.create_configuration_name(name)
                database.add_configuration(path=path, uuid=result["uuid"],
                        name=name, scan=self.scan_version, search=search)

    def scan_configuration(self, database, tree):
        root = tree.getroot()
        file_nodes = root.findall("file")
        if len(file_nodes) == 0:
            print("no files in configuration")
            return
        for file_node in file_nodes:
            name = file_node.find("name").text.strip()
            path = ""
            if file_node.find("sha1") is not None:
                sha1 = file_node.find("sha1").text.strip()
                path = database.find_file(sha1=sha1)
            if not path:
                path = database.find_file(name=name)
                if not path:
                    return
        result = {}

        game_name = ""
        platform_name = ""
        #source_name = ""
        variant_name = ""

        name_node = root.find("name")
        if name_node is not None:
            variant_name = name_node.text.strip()
        #source_node = root.find("source")
        #if source_node is not None:
        #    source_name = source_node.text.strip()
        game_node = root.find("game")
        if game_node is not None:
            game_name_node = game_node.find("name")
            if game_name_node is not None:
                game_name = game_name_node.text.strip()
            game_platform_node = game_node.find("platform")
            if game_platform_node is not None:
                platform_name = game_platform_node.text.strip()

        parts = []
        if platform_name:
            parts.append(platform_name)
        #if source_name:
        #    parts.append(source_name)
        if variant_name:
            parts.append(variant_name)
        if game_name and variant_name:
            result["name"] = u"{0} ({1})".format(game_name, u", ".join(parts))
        result["uuid"] = root.get("uuid", "")
        return result

    def scan_game(self, database, tree, path):
        #print("scan_game")
        root = tree.getroot()
        uuid = root.get("uuid")
        name = root.find("name").text.strip()
        search = name.lower()
        database.add_game(uuid=uuid, path=path, name=name,
                scan=self.scan_version, search=search)

    #def create_configuration_name_from_game_and_variant(self, game, variant):
    #    variant = variant.replace(u", ", u" \u00b7 ")
    #    name = game.strip() + u"\n" + variant.strip()
    #    return name

    #def create_configuration_name_from_path(self, path):
    #    name, ext = os.path.splitext(os.path.basename(path))

    def create_configuration_name(self, name):
        #name, ext = os.path.splitext(name)
        if u"(" in name:
            primary, secondary = name.split(u"(", 1)
            secondary = secondary.replace(u", ", u" \u00b7 ")
            #name = primary.rstrip() + u" \u2013 " + secondary.lstrip()
            name = primary.rstrip() + u"\n" + secondary.lstrip()
            if name[-1] == u")":
                name = name[:-1]
        #text = u" " + text
        return name
