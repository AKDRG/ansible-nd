# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

"""
Argument-spec helpers for nd_vrf.py.

Defined in module_utils (not in plugins/modules/nd_vrf.py) so that strategy
files can import them at the top level without creating a circular dependency
(nd_vrf.py → strategies → nd_vrf.py).
"""


def vrf_base_argument_spec():
    """Argument spec for a single VRF config entry (standalone / child fabrics)."""
    return dict(
        vrf_name=dict(type="str", required=True),
        vrf_template=dict(type="str", default="Default_VRF_Universal"),
        vrf_id=dict(type="int"),
        vlan_id=dict(type="int"),
        deploy=dict(type="bool", default=True),
        attach=dict(
            type="list",
            elements="dict",
            default=[],
            options=dict(
                ip_address=dict(type="str", required=True),
                vlan_id=dict(type="int"),
                deploy=dict(type="bool", default=True),
                vrf_lite=dict(type="list", elements="dict", default=[]),
            ),
        ),
    )


def _child_fabric_config_element_spec():
    """Argument spec for one entry inside child_fabric_config."""
    return dict(
        fabric=dict(type="str", required=True),
        attach=dict(
            type="list",
            elements="dict",
            default=[],
            options=dict(
                ip_address=dict(type="str", required=True),
                vlan_id=dict(type="int"),
                deploy=dict(type="bool", default=False),
                vrf_lite=dict(type="list", elements="dict", default=[]),
            ),
        ),
    )


def vrf_parent_argument_spec():
    """Argument spec for a VRF config entry on parent (MSD / MFD) fabrics."""
    spec = vrf_base_argument_spec()
    spec["child_fabric_config"] = dict(
        type="list",
        elements="dict",
        default=[],
        options=_child_fabric_config_element_spec(),
    )
    return spec
