from typing import Any, Dict, List, Optional

from pydantic import Field, model_validator

from laktory.models.basemodel import BaseModel
from laktory.models.resources.baseresource import ResourceLookup
from laktory.models.resources.pulumiresource import PulumiResource
from laktory.models.resources.terraformresource import TerraformResource


class AccessControlRuleSetGrant(BaseModel):
    """
    Databricks Access Control Rule Set Grant

    Attributes
    ----------
    principal:
        Principal identifier string. Examples: 'users/example@example.com', 'groups/admins', 'service-principals/abc-123'
    role:
        Role to grant to the principal. Examples: 'ADMIN', 'USER', 'MANAGER'
    """

    principal: str
    role: str


class AccessControlRuleSet(BaseModel, PulumiResource, TerraformResource):
    """
    Databricks Access Control Rule Set

    Access Control Rule Sets allow setting permissions on service principals and other account-level resources.

    Attributes
    ----------
    name:
        Name of the Access Control Rule Set.
    description:
        Description of the Access Control Rule Set.
    grant_rules:
        List of grant rules to apply.

    Examples
    --------
    ```py
    from laktory import models

    ruleset = models.resources.databricks.AccessControlRuleSet(
        name="my-access-control-rule-set",
        description="Access control rules for service principals",
        grant_rules=[
            models.resources.databricks.AccessControlRuleSetGrant(
                principal="service-principals/abc-123",
                role="ADMIN"
            ),
            models.resources.databricks.AccessControlRuleSetGrant(
                principal="groups/data-engineers",
                role="USER"
            )
        ]
    )
    ```
    """

    name: str
    description: Optional[str] = None
    grant_rules: List[AccessControlRuleSetGrant] = Field(default_factory=list)

    @property
    def terraform_resource_type(self) -> str:
        """Terraform resource type"""
        return "databricks_access_control_rule_set"
    
    @property
    def pulumi_resource_type(self) -> str:
        """Pulumi resource type"""
        return "databricks:AccessControlRuleSet"

    @property
    def resource_id(self) -> str:
        """Resource ID"""
        return self.name

    def terraform_resource_args(self) -> Dict[str, Any]:
        """Terraform resource arguments"""
        args = {
            "name": self.name,
        }
        
        if self.description is not None:
            args["description"] = self.description
            
        if self.grant_rules:
            args["grant_rules"] = [
                {"principal": g.principal, "role": g.role}
                for g in self.grant_rules
            ]
            
        return args
    
    def pulumi_resource_args(self) -> Dict[str, Any]:
        """Pulumi resource arguments"""
        # For this resource, Pulumi args are the same as Terraform args
        return self.terraform_resource_args()

    @model_validator(mode="after")
    def validate_model(self) -> Any:
        """
        Validate the model.

        Returns
        -------
        Any
            The validated model.
        """
        if not self.grant_rules:
            raise ValueError("At least one grant rule must be specified.")

        return self
