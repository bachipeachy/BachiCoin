#!/usr/bin/env python3
"""net_validation.py - static methods for validating data against schema and business rules"""

from datetime import datetime
from typing import Dict, List, Any

from BachiCoin.lib_network.net_config import NetConfig, NodeType, NodeStatus

class NetValidation:
    """A collection of pure, static methods for node data validation."""

    @staticmethod
    def validate_field_by_schema(field_name: str, value: Any) -> List[str]:
        """Validates a single field's value against the master schema."""
        errors = []
        constraints = NetConfig._NODE_MASTER_SCHEMA.get(field_name)

        if not constraints:
            return [f"'{field_name}' is not a valid field in the node schema."]

        # Required check
        if constraints.get("required") and (value is None or value == ""):
            errors.append(f"'{field_name}' is required")
            return errors

        if value is None:
            return []

        # Type check
        expected_type = constraints.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(f"'{field_name}' must be of type {expected_type.__name__}, but got {type(value).__name__}")
            return errors

        # List validations
        if isinstance(value, list) and "max_items" in constraints and len(value) > constraints["max_items"]:
            errors.append(f"'{field_name}' exceeds the maximum item count of {constraints['max_items']}")

        # Allowed values check
        allowed = constraints.get("allowed_values")
        if allowed and value not in allowed:
            errors.append(f"'{value}' is not an allowed value for '{field_name}'")

        return errors

    @staticmethod
    def validate_required_fields(node_data: Dict[str, Any], view: str) -> List[str]:
        """Validates that all required fields for a given view are present."""
        errors = []
        schema_view = NetConfig.get_node_schema_view(view)
        
        for field, constraints in schema_view.items():
            if constraints.get("required") and (node_data.get(field) is None or node_data.get(field) == ""):
                errors.append(f"Missing required field for '{view}' view: '{field}'")
        return errors

    @staticmethod
    def validate_field_formats(node_data: Dict[str, Any]) -> List[str]:
        """Validates specific field formats like node_id."""
        errors = []
        if node_data.get("node_id") and not NetConfig.NODE_ID_PATTERN.match(node_data["node_id"]):
            errors.append("Invalid 'node_id' format")
        return errors

    @staticmethod
    def is_valid_iso_timestamp(timestamp: str) -> bool:
        """Validates if a string is a compliant ISO 8601 timestamp."""
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_timestamps(node_data: Dict[str, Any]) -> List[str]:
        """Validates that timestamp fields are in the correct ISO 8601 format."""
        errors = []
        for field in ["created_at", "last_seen"]:
            if node_data.get(field) and not NetValidation.is_valid_iso_timestamp(node_data[field]):
                errors.append(f"Invalid ISO 8601 format for '{field}'")
        return errors

    @staticmethod
    def validate_node_data(node_data: Dict[str, Any], view: str = "full_schema") -> List[str]:
        """
        Main validation entry point. Runs a comprehensive set of checks."""
        errors = NetValidation.validate_required_fields(node_data, view)
        errors.extend(NetValidation.validate_field_formats(node_data))
        errors.extend(NetValidation.validate_timestamps(node_data))

        for field, value in node_data.items():
            errors.extend(NetValidation.validate_field_by_schema(field, value))

        return sorted(list(set(errors)))

    @staticmethod
    def validate_for_update(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> List[str]:
        """Validates a proposed update against the current node data."""
        errors = []
        immutable_fields = NetConfig.get_immutable_fields()
        
        for field in immutable_fields:
            if field in update_data and update_data[field] != current_data.get(field):
                errors.append(f"Cannot update immutable field: '{field}'")

        if errors:
            return errors

        merged_data = {**current_data, **update_data}
        errors.extend(NetValidation.validate_node_data(merged_data, "full_schema"))

        return sorted(list(set(errors)))

    @staticmethod
    def validate_peer_data(peer_data: Dict[str, Any]) -> bool:
        """Placeholder for peer data validation. Always returns True for now."""
        # In a real scenario, this would validate peer structure, URL, etc.
        return True

def assert_valid_node_data(node_data: Dict[str, Any], view: str = "full_schema") -> None:
    """Asserts that node data is valid for a given view, failing fast if not."""
    errors = NetValidation.validate_node_data(node_data, view)
    assert not errors, f"Node data validation failed: {errors}"

def assert_valid_update_data(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> None:
    """Asserts that an update is valid, failing fast if not."""
    errors = NetValidation.validate_for_update(current_data, update_data)
    assert not errors, f"Node update validation failed: {errors}"

if __name__ == "__main__":
    """A simple smoke test to verify that the validation module can be loaded."""
    print("--- Running NetValidation Smoke Test ---")
    
    # 1. Test a valid field
    valid_node_id = "N_a1b2c3d4e5f6a7b8"
    errors = NetValidation.validate_field_by_schema("node_id", valid_node_id)
    assert not errors, f"Validation of a valid node_id failed: {errors}"
    print("✅ Validation of a single valid field works.")

    # 2. Test an invalid field format
    invalid_node_id = "invalid-id"
    errors = NetValidation.validate_field_formats({"node_id": invalid_node_id})
    assert errors, "Validation of an invalid node_id should have failed."
    print("✅ Detection of an invalid field format works.")

    # 3. Test required fields for 'create' view
    incomplete_data = {"node_url": "http://test.com"}
    errors = NetValidation.validate_required_fields(incomplete_data, "create")
    assert "Missing required field for 'create' view: 'ip_address'" in errors, "Required field check failed."
    print("✅ Required field check works.")

    # 4. Test the main entry point with a valid payload
    valid_node = {
        "node_id": "N_a1b2c3d4e5f6a7b8",
        "node_url": "http://my-node.com:9333",
        "ip_address": "192.168.1.1",
        "p2p_port": 9333,
        "node_type": NodeType.FULL_NODE.value,
        "status": NodeStatus.ACTIVE.value,
        "created_at": "2023-01-01T00:00:00Z",
        "last_seen": "2023-01-01T00:00:00Z"
    }
    errors = NetValidation.validate_node_data(valid_node, "full_schema")
    assert not errors, f"Validation of a valid node object failed: {errors}"
    print("✅ Full validation of a valid node object works.")

    # 5. Test immutable field update
    current_node = valid_node.copy()
    update_attempt = {"node_id": "N_c1d2e3f4a5b6c7d8"}
    errors = NetValidation.validate_for_update(current_node, update_attempt)
    assert "Cannot update immutable field: 'node_id'" in errors, "Immutable field check failed."
    print("✅ Detection of immutable field update works.")

    # 6. Test placeholder peer validation
    assert NetValidation.validate_peer_data({"peer_url": "http://peer.com"}), "Placeholder peer validation failed."
    print("✅ Placeholder peer validation works.")

    print("\n--- NetValidation Smoke Test Passed Successfully! ---")
