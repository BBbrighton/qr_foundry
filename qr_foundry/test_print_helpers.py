#!/usr/bin/env python3
"""
Test script for QR Foundry print helpers
Run this with: bench execute qr_foundry.test_print_helpers.run_tests
"""

import frappe
from qr_foundry.print_helpers import qr_data_uri, embed_file


def run_tests():
    """Run all print helper tests"""
    print("🧪 QR Foundry Print Helpers Test Suite")
    print("=" * 50)
    
    # Test 1: QR Settings accessibility
    test_qr_settings()
    
    # Test 2: QR data URI generation
    test_qr_data_uri()
    
    # Test 3: File embedding
    test_embed_file()
    
    # Test 4: Jinja method registration
    test_jinja_registration()
    
    print("\n✅ All tests completed!")


def test_qr_settings():
    """Test QR Settings access"""
    print("\n1️⃣ Testing QR Settings access...")
    
    try:
        settings = frappe.get_single("QR Settings")
        private_setting = getattr(settings, "store_images_private", 0)
        print(f"   ✅ QR Settings accessible")
        print(f"   📁 Store images private: {bool(private_setting)}")
        
        if private_setting:
            print("   🔒 Privacy mode is enabled (good!)")
        else:
            print("   ⚠️  Privacy mode is disabled")
            
    except Exception as e:
        print(f"   ❌ Error accessing QR Settings: {e}")


def test_qr_data_uri():
    """Test QR data URI generation"""
    print("\n2️⃣ Testing QR data URI generation...")
    
    # Test with User doctype (should always exist)
    test_doctype = "User"
    test_users = frappe.get_all("User", limit=1, fields=["name"])
    
    if not test_users:
        print("   ⚠️  No users found for testing")
        return
        
    test_name = test_users[0]["name"]
    
    try:
        data_uri = qr_data_uri(test_doctype, test_name)
        
        if data_uri and data_uri.startswith("data:image/png;base64,"):
            print(f"   ✅ QR data URI generated successfully")
            print(f"   📋 Doctype: {test_doctype}, Name: {test_name}")
            print(f"   📏 Data URI length: {len(data_uri)} characters")
            print(f"   🔗 Starts with: {data_uri[:50]}...")
        else:
            print(f"   ❌ Invalid data URI format: {data_uri[:100] if data_uri else 'None'}")
            
    except Exception as e:
        print(f"   ❌ Error generating QR data URI: {e}")
        import traceback
        print(f"   🔍 Traceback: {traceback.format_exc()}")


def test_embed_file():
    """Test file embedding functionality"""
    print("\n3️⃣ Testing file embedding...")
    
    # Test with a small test file if available
    try:
        # Look for any existing file in the system
        files = frappe.get_all("File", 
                             filters={"is_private": 0}, 
                             fields=["name", "file_url", "file_size"], 
                             limit=1,
                             order_by="file_size asc")
        
        if files:
            test_file = files[0]
            print(f"   📁 Testing with file: {test_file['file_url']}")
            
            try:
                embedded = embed_file(test_file["file_url"])
                if embedded and embedded.startswith("data:"):
                    print(f"   ✅ File embedded successfully")
                    print(f"   📏 Embedded data length: {len(embedded)} characters")
                    print(f"   🔗 Starts with: {embedded[:50]}...")
                else:
                    print(f"   ❌ Invalid embedded format: {embedded[:100] if embedded else 'None'}")
            except Exception as e:
                print(f"   ❌ Error embedding file: {e}")
        else:
            print("   ⚠️  No public files found for testing")
            
    except Exception as e:
        print(f"   ❌ Error finding test files: {e}")


def test_jinja_registration():
    """Test if Jinja methods are properly registered"""
    print("\n4️⃣ Testing Jinja method registration...")
    
    try:
        from frappe.utils.jinja import get_jenv
        jenv = get_jenv()
        
        # Check if our methods are available in Jinja environment
        methods_to_check = ["qr_data_uri", "embed_file"]
        
        for method_name in methods_to_check:
            if method_name in jenv.globals:
                print(f"   ✅ {method_name} is registered in Jinja")
            else:
                print(f"   ❌ {method_name} is NOT registered in Jinja")
                
        print(f"   📊 Total Jinja globals: {len(jenv.globals)}")
        
    except Exception as e:
        print(f"   ❌ Error checking Jinja registration: {e}")


def test_with_specific_doctype(doctype_name, doc_name=None):
    """Test QR generation with a specific doctype and document"""
    print(f"\n🎯 Testing with specific doctype: {doctype_name}")
    
    if not doc_name:
        # Find a document of this type
        docs = frappe.get_all(doctype_name, limit=1, fields=["name"])
        if not docs:
            print(f"   ⚠️  No {doctype_name} documents found")
            return
        doc_name = docs[0]["name"]
    
    try:
        data_uri = qr_data_uri(doctype_name, doc_name)
        print(f"   ✅ QR generated for {doctype_name}: {doc_name}")
        print(f"   📏 Length: {len(data_uri)} characters")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


if __name__ == "__main__":
    # This allows running the script directly for testing
    run_tests()