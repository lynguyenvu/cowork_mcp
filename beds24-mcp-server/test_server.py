#!/usr/bin/env python3
"""
Test script for Beds24 MCP Server.

Tests input validation, error handling, and response formatting
without requiring actual API credentials.

Run with: python test_server.py
"""

import sys


def test_input_validation():
    """Test Pydantic input validation models."""
    print("=" * 60)
    print("Testing Input Validation")
    print("=" * 60)

    from server import (
        CreateBookingInput,
        ListBookingsInput,
        CheckAvailabilityInput,
        UpdateCalendarInput,
    )

    passed = 0
    failed = 0

    # Test 1: Valid booking input
    print("\n1. Testing valid CreateBookingInput...")
    try:
        booking = CreateBookingInput(
            property_id="12345",
            check_in="2024-03-15",
            check_out="2024-03-20",
            guest_name="John Doe",
            guest_email="john@example.com",
        )
        print(f"   ✅ Valid input accepted")
        passed += 1
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        failed += 1

    # Test 2: Invalid email
    print("\n2. Testing invalid email validation...")
    try:
        booking = CreateBookingInput(
            property_id="12345",
            check_in="2024-03-15",
            check_out="2024-03-20",
            guest_name="John Doe",
            guest_email="invalid-email",
        )
        print(f"   ❌ Should have rejected invalid email")
        failed += 1
    except Exception as e:
        print(f"   ✅ Correctly rejected invalid email")
        passed += 1

    # Test 3: Check-out before check-in
    print("\n3. Testing check-out before check-in...")
    try:
        booking = CreateBookingInput(
            property_id="12345",
            check_in="2024-03-20",
            check_out="2024-03-15",
            guest_name="John Doe",
            guest_email="john@example.com",
        )
        print(f"   ❌ Should have rejected invalid date order")
        failed += 1
    except Exception as e:
        print(f"   ✅ Correctly rejected invalid date order")
        passed += 1

    # Test 4: Limit validation
    print("\n4. Testing limit range validation...")
    try:
        input_data = ListBookingsInput(limit=200)  # Over max of 100
        print(f"   ❌ Should have rejected limit > 100")
        failed += 1
    except Exception as e:
        print(f"   ✅ Correctly rejected limit > 100")
        passed += 1

    # Test 5: Negative limit
    print("\n5. Testing negative limit validation...")
    try:
        input_data = ListBookingsInput(limit=-1)
        print(f"   ❌ Should have rejected negative limit")
        failed += 1
    except Exception as e:
        print(f"   ✅ Correctly rejected negative limit")
        passed += 1

    # Test 6: Valid availability check
    print("\n6. Testing valid CheckAvailabilityInput...")
    try:
        avail = CheckAvailabilityInput(
            property_id="12345",
            check_in="2024-03-15",
            check_out="2024-03-20",
        )
        print(f"   ✅ Valid availability input accepted")
        passed += 1
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        failed += 1

    print(f"\n📊 Input Validation: {passed}/{passed + failed} tests passed")
    return failed == 0


def test_error_handling():
    """Test error handling utilities."""
    print("\n" + "=" * 60)
    print("Testing Error Handling")
    print("=" * 60)

    import httpx
    from server import _handle_api_error

    passed = 0
    failed = 0

    # Test 404 error
    print("\n1. Testing 404 error handling...")
    try:
        raise httpx.HTTPStatusError(
            "Not found",
            request=httpx.Request("GET", "https://api.test.com/bookings/999"),
            response=httpx.Response(404)
        )
    except httpx.HTTPStatusError as e:
        result = _handle_api_error(e)
        if "not found" in result.lower():
            print(f"   ✅ Correctly handled 404")
            passed += 1
        else:
            print(f"   ❌ Unexpected 404 message: {result}")
            failed += 1

    # Test 401 error
    print("\n2. Testing 401 error handling...")
    try:
        raise httpx.HTTPStatusError(
            "Unauthorized",
            request=httpx.Request("GET", "https://api.test.com/bookings"),
            response=httpx.Response(401)
        )
    except httpx.HTTPStatusError as e:
        result = _handle_api_error(e)
        if "authentication" in result.lower() or "invalid" in result.lower():
            print(f"   ✅ Correctly handled 401")
            passed += 1
        else:
            print(f"   ❌ Unexpected 401 message: {result}")
            failed += 1

    # Test 429 error
    print("\n3. Testing 429 rate limit handling...")
    try:
        raise httpx.HTTPStatusError(
            "Rate limited",
            request=httpx.Request("GET", "https://api.test.com/bookings"),
            response=httpx.Response(429)
        )
    except httpx.HTTPStatusError as e:
        result = _handle_api_error(e)
        if "rate limit" in result.lower():
            print(f"   ✅ Correctly handled 429")
            passed += 1
        else:
            print(f"   ❌ Unexpected 429 message: {result}")
            failed += 1

    # Test timeout
    print("\n4. Testing timeout handling...")
    try:
        raise httpx.TimeoutException("Request timed out")
    except Exception as e:
        result = _handle_api_error(e)
        if "timeout" in result.lower() or "timed out" in result.lower():
            print(f"   ✅ Correctly handled timeout")
            passed += 1
        else:
            print(f"   ❌ Unexpected timeout message: {result}")
            failed += 1

    # Test connection error
    print("\n5. Testing connection error handling...")
    try:
        raise httpx.ConnectError("Connection failed")
    except Exception as e:
        result = _handle_api_error(e)
        if "connect" in result.lower() or "network" in result.lower():
            print(f"   ✅ Correctly handled connection error")
            passed += 1
        else:
            print(f"   ❌ Unexpected connection error message: {result}")
            failed += 1

    print(f"\n📊 Error Handling: {passed}/{passed + failed} tests passed")
    return failed == 0


def test_response_formatting():
    """Test response formatting utilities."""
    print("\n" + "=" * 60)
    print("Testing Response Formatting")
    print("=" * 60)

    from server import (
        _format_markdown_booking,
        _format_markdown_property,
        _format_timestamp,
    )

    passed = 0
    failed = 0

    # Test booking formatting
    print("\n1. Testing booking markdown formatting...")
    booking_data = {
        "id": "BOOK-123",
        "status": "confirmed",
        "checkIn": "2024-03-15",
        "checkOut": "2024-03-20",
        "guestName": "John Doe",
        "guestEmail": "john@example.com",
        "propertyName": "Grand Hotel",
        "totalPrice": 500.00
    }
    result = _format_markdown_booking(booking_data)
    result_upper = result.upper()
    if "BOOK-123" in result and "CONFIRMED" in result_upper:
        print(f"   ✅ Booking formatted correctly")
        passed += 1
    else:
        print(f"   ❌ Booking formatting failed")
        print(f"       Result: {result[:100]}...")
        failed += 1

    # Test property formatting
    print("\n2. Testing property markdown formatting...")
    property_data = {
        "id": "12345",
        "name": "Grand Hotel",
        "address": {
            "city": "New York",
            "country": "USA"
        }
    }
    result = _format_markdown_property(property_data)
    if "Grand Hotel" in result and "12345" in result:
        print(f"   ✅ Property formatted correctly")
        passed += 1
    else:
        print(f"   ❌ Property formatting failed")
        failed += 1

    # Test timestamp formatting
    print("\n3. Testing timestamp formatting...")
    result = _format_timestamp(1710489600)  # Unix timestamp
    if "2024" in result:
        print(f"   ✅ Timestamp formatted: {result}")
        passed += 1
    else:
        print(f"   ❌ Timestamp formatting failed: {result}")
        failed += 1

    print(f"\n📊 Response Formatting: {passed}/{passed + failed} tests passed")
    return failed == 0


def test_tool_count():
    """Test that expected number of tools are defined."""
    print("\n" + "=" * 60)
    print("Testing Tool Count")
    print("=" * 60)

    # Count tool functions in server module
    import server
    tool_functions = [name for name in dir(server) if name.startswith('beds24_')]

    expected_tools = [
        "beds24_list_bookings",
        "beds24_get_booking",
        "beds24_create_booking",
        "beds24_update_booking",
        "beds24_cancel_booking",
        "beds24_list_properties",
        "beds24_get_property",
        "beds24_list_property_rooms",
        "beds24_check_availability",
        "beds24_get_calendar",
        "beds24_update_calendar",
        "beds24_get_pricing_offers",
    ]

    print(f"\nExpected {len(expected_tools)} tools:")
    for tool in expected_tools:
        status = "✅" if tool in tool_functions else "❌"
        print(f"  {status} {tool}")

    found = sum(1 for t in expected_tools if t in tool_functions)
    total = len(expected_tools)

    print(f"\n📊 Tool Count: {found}/{total} tools found")
    return found == total


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Beds24 MCP Server - Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Input Validation", test_input_validation()))
    results.append(("Error Handling", test_error_handling()))
    results.append(("Response Formatting", test_response_formatting()))
    results.append(("Tool Count", test_tool_count()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")

    print(f"\n📊 Total: {passed}/{total} test suites passed")

    if passed == total:
        print("\n🎉 All tests passed! MCP server is ready for deployment.")
        return 0
    else:
        print("\n❌ Some tests failed. Please fix the issues before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())