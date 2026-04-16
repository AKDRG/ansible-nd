# Copyright: (c) 2026, Akshayanat C S (@achengam) <achengam@cisco.com>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

from typing import Any, Dict, Optional, Type

from ansible_collections.cisco.nd.plugins.module_utils.models.manage_vrfs.config_models import (
    VrfConfigModel,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.vrf_argument_specs import (
    vrf_base_argument_spec,
)
from ansible_collections.cisco.nd.plugins.module_utils.orchestrators.strategies.base_vrf import (
    BaseVrfStrategy,
)
from ansible_collections.cisco.nd.plugins.module_utils.endpoints.v1.manage.manage_fabrics_vrfs import (
    EpManageFabricsVrfsGet,
    EpManageFabricsVrfsPost,
    EpManageFabricsVrfsVrfNamePut,
    EpManageFabricsVrfsVrfNameDelete,
)
from ansible_collections.cisco.nd.plugins.module_utils.endpoints.v1.manage.manage_fabrics_vrfactions import (
    EpManageFabricsVrfActionsDeployPost,
    EpManageFabricsVrfActionsRemovePost,
)


class StandaloneVrfStrategy(BaseVrfStrategy):
    """
    Strategy for standalone (non-Multisite / non-Multicluster) fabrics.

    Uses the standard /api/v1/manage/fabrics/{fabricName}/vrfs endpoints.
    No child fabric orchestration.
    """

    @property
    def fabric_type(self) -> str:
        return "standalone"

    @property
    def config_model_cls(self) -> type:
        return VrfConfigModel

    def get_argument_spec(self) -> Dict[str, Any]:
        """Standalone fabrics use the base VRF argument spec (no child_fabric_config)."""
        return vrf_base_argument_spec()

    # ── Endpoint classes ──────────────────────────────────────────

    def vrfs_get_cls(self) -> Type:
        return EpManageFabricsVrfsGet

    def vrfs_post_cls(self) -> Type:
        return EpManageFabricsVrfsPost

    def vrf_put_cls(self) -> Type:
        return EpManageFabricsVrfsVrfNamePut

    def vrf_delete_cls(self) -> Type:
        return EpManageFabricsVrfsVrfNameDelete

    def vrf_actions_deploy_post_cls(self) -> Type:
        return EpManageFabricsVrfActionsDeployPost

    def vrf_actions_remove_post_cls(self) -> Type:
        return EpManageFabricsVrfActionsRemovePost

    # ── Query params ──────────────────────────────────────────────

    def build_query_all_params(self, **kwargs) -> Optional[Dict[str, Any]]:
        return {"fabricName": self.fabric_name}
