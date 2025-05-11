import pytest

from laktory.models.resources.databricks import AccessControlRuleSet, AccessControlRuleSetGrant


def test_accesscontrolruleset_basic():
    """Test basic AccessControlRuleSet functionality."""
    ruleset = AccessControlRuleSet(
        name="my-access-control-rule-set",
        description="Access control rules for service principals",
        grant_rules=[
            AccessControlRuleSetGrant(
                principal="service-principals/abc-123",
                role="ADMIN"
            ),
            AccessControlRuleSetGrant(
                principal="groups/data-engineers",
                role="USER"
            )
        ]
    )
    
    # Check basic properties
    assert ruleset.name == "my-access-control-rule-set"
    assert ruleset.description == "Access control rules for service principals"
    assert len(ruleset.grant_rules) == 2
    
    # Check resource type and ID
    assert ruleset.terraform_resource_type == "databricks_access_control_rule_set"
    assert ruleset.pulumi_resource_type == "databricks:AccessControlRuleSet"
    assert ruleset.resource_id == "my-access-control-rule-set"
    
    # Check terraform resource arguments
    terraform_args = ruleset.terraform_resource_args()
    assert terraform_args["name"] == "my-access-control-rule-set"
    assert terraform_args["description"] == "Access control rules for service principals"
    assert len(terraform_args["grant_rules"]) == 2
    assert terraform_args["grant_rules"][0]["principal"] == "service-principals/abc-123"
    assert terraform_args["grant_rules"][0]["role"] == "ADMIN"
    assert terraform_args["grant_rules"][1]["principal"] == "groups/data-engineers"
    assert terraform_args["grant_rules"][1]["role"] == "USER"
    
    # Check pulumi resource arguments
    pulumi_args = ruleset.pulumi_resource_args()
    assert pulumi_args == terraform_args


def test_accesscontrolruleset_validation():
    """Test AccessControlRuleSet validation."""
    # Test validation for empty grant_rules
    with pytest.raises(ValueError, match="At least one grant rule must be specified"):
        AccessControlRuleSet(
            name="my-access-control-rule-set",
            description="Access control rules for service principals",
            grant_rules=[]
        )
