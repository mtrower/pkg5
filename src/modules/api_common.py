#!/usr/bin/python
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# Visible changes to classes here require an update to
# doc/client_api_versions.txt and/or doc/server_api_versions.txt.

"""Contains API functions and classes common to both pkg.client.api and
pkg.server.api."""

import pkg.client.image  as image
import pkg.fmri as fmri
import pkg.misc as misc

class LicenseInfo(object):
        """A class representing the license information a package
        provides.  Not intended for instantiation by API consumers."""

        def __init__(self, pfmri, act, img=None, text=None):
                self.__action = act
                self.__fmri = pfmri
                self.__img = img
                self.__text = text

        def __str__(self):
                return self.get_text()

        def get_text(self):
                """Retrieves and returns the payload of the license (which
                should be text).  This may require remote retrieval of
                resources and so this could raise a TransportError or other
                ApiException."""

                if not self.__img:
                        return self.__text
                return self.__action.get_text(self.__img, self.__fmri)

        @property
        def fmri(self):
                """The FMRI of the package this license is for."""

                return self.__fmri

        @property
        def license(self):
                """The keyword identifying this license within its related
                package."""

                return self.__action.attrs["license"]

        @property
        def must_accept(self):
                """A boolean value indicating whether the license requires
                acceptance."""

                return self.__action.must_accept

        @property
        def must_display(self):
                """A boolean value indicating whether the license must be
                displayed during install or update operations."""

                return self.__action.must_display


class PackageCategory(object):
        """Represents the scheme and category of an info.classification entry
        for a package."""

        scheme = None
        category = None

        def __init__(self, scheme, category):
                self.scheme = scheme
                self.category = category

        def __str__(self, verbose=False):
                if verbose:
                        return "%s (%s)" % (self.category, self.scheme)
                else:
                        return "%s" % self.category


class PackageInfo(object):
        """A class capturing the information about packages that a client
        could need. The fmri is guaranteed to be set. All other values may
        be None, depending on how the PackageInfo instance was created."""

        # Possible package installation states; these constants should match
        # the values used by the Image class.  Constants with negative values
        # are not currently available.
        FROZEN = -1
        INCORPORATED = -2
        EXCLUDES = -3
        KNOWN = image.Image.PKG_STATE_KNOWN
        INSTALLED = image.Image.PKG_STATE_INSTALLED
        UPGRADABLE = image.Image.PKG_STATE_UPGRADABLE
        OBSOLETE = image.Image.PKG_STATE_OBSOLETE
        RENAMED = image.Image.PKG_STATE_RENAMED

        __NUM_PROPS = 13
        IDENTITY, SUMMARY, CATEGORIES, STATE, PREF_PUBLISHER, SIZE, LICENSES, \
            LINKS, HARDLINKS, FILES, DIRS, DEPENDENCIES, DESCRIPTION = \
            range(__NUM_PROPS)
        ALL_OPTIONS = frozenset(range(__NUM_PROPS))
        ACTION_OPTIONS = frozenset([LINKS, HARDLINKS, FILES, DIRS,
            DEPENDENCIES])

        def __init__(self, pfmri, pkg_stem=None, summary=None,
            category_info_list=None, states=None, publisher=None,
            preferred_publisher=None, version=None, build_release=None,
            branch=None, packaging_date=None, size=None, licenses=None,
            links=None, hardlinks=None, files=None, dirs=None,
            dependencies=None, description=None):
                self.pkg_stem = pkg_stem
                self.summary = summary
                if category_info_list is None:
                        category_info_list = []
                self.category_info_list = category_info_list
                self.states = states
                self.publisher = publisher
                self.preferred_publisher = preferred_publisher
                self.version = version
                self.build_release = build_release
                self.branch = branch
                self.packaging_date = packaging_date
                self.size = size
                self.fmri = pfmri
                self.licenses = licenses
                self.links = links
                self.hardlinks = hardlinks
                self.files = files
                self.dirs = dirs
                self.dependencies = dependencies
                self.description = description

        def __str__(self):
                return self.fmri

        @staticmethod
        def build_from_fmri(f):
                if not f:
                        return f
                pub, name, version = f.tuple()
                pub = fmri.strip_pub_pfx(pub)
                return PackageInfo(pkg_stem=name, publisher=pub,
                    version=version.release,
                    build_release=version.build_release, branch=version.branch,
                    packaging_date=version.get_timestamp().strftime("%c"),
                    pfmri=str(f))


def _get_pkg_cat_data(cat, info_needed, actions=None,
    excludes=misc.EmptyI, pfmri=None):
        """This is a private method and not intended for
        external consumers."""

        # XXX this doesn't handle locale.
        get_summ = summ = desc = cat_info = deps = None
        cat_data = []
        get_summ = PackageInfo.SUMMARY in info_needed
        if PackageInfo.CATEGORIES in info_needed:
                cat_info = []
        if PackageInfo.DEPENDENCIES in info_needed:
                cat_data.append(cat.DEPENDENCY)
                deps = []

        if deps is None or len(info_needed) != 1:
                # Anything other than dependency data
                # requires summary data.
                cat_data.append(cat.SUMMARY)

        if actions is None:
                actions = cat.get_entry_actions(pfmri, cat_data,
                    excludes=excludes)

        for a in actions:
                if deps is not None and a.name == "depend":
                        deps.append(a.attrs.get(a.key_attr))
                        continue
                elif a.name != "set":
                        continue

                attr_name = a.attrs["name"]
                if attr_name == "pkg.summary":
                        if get_summ:
                                summ = a.attrs["value"]
                elif attr_name == "description":
                        if get_summ and summ is None:
                                # Historical summary field.
                                summ = a.attrs["value"]
                elif attr_name == "pkg.description":
                        desc = a.attrs["value"]
                elif cat_info != None and a.has_category_info():
                        cat_info.extend(a.parse_category_info())

        if get_summ and summ is None:
                if desc is None:
                        summ = ""
                else:
                        summ = desc
        if not PackageInfo.DESCRIPTION in info_needed:
                desc = None
        return summ, desc, cat_info, deps