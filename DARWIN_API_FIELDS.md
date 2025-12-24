# Darwin API - Complete Field Reference

## API Endpoint
- **URL**: `https://apexon-peoplehubuat.darwinbox.in/masterapi/employee`
- **Method**: GET (with JSON body) or POST
- **Authentication**: Basic Auth
  - Username: `apexon_nest`
  - Password: `Apexon@nest@321`

## Request Format

```json
{
  "api_key": "YOUR_API_KEY_HERE",
  "datasetKey": "d7dd623e21a8460abbc9549b413c523ed4f2822b4800414eb78eea7f730f894874d205b35f531a2355b6438982e3d200741313991e25d5b0db8b2b16703c44e1",
  "last_modified": "01-01-2025",
  "employee_ids": []  // Empty array to get all employees
}
```

## Response Structure

```json
{
  "status": 1,
  "message": "Successfully loaded all employees data",
  "employee_data": [ /* array of employee objects */ ]
}
```

---

## Employee Fields (Available from Darwin API)

### ✅ Basic Information

| Field Name | Type | Description | Example | Availability |
|------------|------|-------------|---------|--------------|
| `employee_id` | String | Unique employee identifier | `"200088"` | ✅ Always |
| `first_name` | String | Employee's first name | `"Abdul"` | ✅ Always |
| `last_name` | String | Employee's last name | `"Mohammed"` | ✅ Always |

### ✅ Manager Information

| Field Name | Type | Description | Example | Availability |
|------------|------|-------------|---------|--------------|
| `direct_manager_employee_id` | String | Direct manager's employee ID | `"202895"` | ✅ 95% |
| `direct_manager_email` | String | Direct manager's email | `"testcheck@gmail.com"` | ✅ 95% |

**Note**: Direct manager is used for both Hiring Manager and Reporting Manager roles.

### ✅ HRBP Information

| Field Name | Type | Description | Example | Availability |
|------------|------|-------------|---------|--------------|
| `hrbp_employee_id` | String | HRBP's employee ID | `"200016"` | ✅ 90% |
| `hrbp_email_id` | String | HRBP's email | `"Vishal.Sarada@apexon.com.com"` | ✅ 90% |

### ❌ Not Available

| Information | Status | Notes |
|------------|--------|-------|
| **Recruiter Info** | ❌ Not Available | Darwin API does not provide recruiter information |
| **Email** | ❌ Not Available | Employee email is not in Darwin API response |
| **Role Title** | ❌ Not Available | Job title/designation not in Darwin API |
| **Start Date** | ❌ Not Available | Date of joining not in Darwin API |
| **Location/Timezone** | ❌ Not Available | Location information not in Darwin API |
| **Phone Numbers** | ❌ Not Available | Contact numbers not in Darwin API |
| **Address** | ❌ Not Available | Address information not in Darwin API |

---

## Current Statistics (Based on Test Results)

- **Total Employees**: 4,584
- **With Direct Manager**: 4,368 (95%)
- **With HRBP**: 4,138 (90%)
- **With Both**: 4,027 (87%)
- **With Neither**: 105 (2%)

---

## Example Employee Data Structure

```json
{
  "first_name": "Abdul",
  "last_name": "Mohammed",
  "direct_manager_employee_id": "202895",
  "direct_manager_email": "testcheck@gmail.com",
  "employee_id": "200088",
  "hrbp_employee_id": "200016",
  "hrbp_email_id": "Vishal.Sarada@apexon.com.com"
}
```

---

## Field Name Variations Handled

The implementation handles multiple field name formats:

### Primary Format (Underscores)
- `first_name`, `last_name`
- `employee_id`
- `direct_manager_employee_id`, `direct_manager_email`
- `hrbp_employee_id`, `hrbp_email_id`

### Fallback Formats
- Spaces: `"first name"`, `"direct manager email"`, etc.
- CamelCase: `firstName`, `employeeId`, etc.

---

## Mapping to Application Entities

### Candidate Entity
- **ID**: `employee_id` from Darwin API
- **Name**: `first_name` + `last_name`
- **Email**: Generated (not in Darwin API)
- **Role Title**: Default "Employee" (not in Darwin API)
- **Start Date**: Default (today + 14 days)
- **Timezone**: Default "Asia/Kolkata"
- **Hiring Manager ID**: Derived from `direct_manager_email`
- **Reporting Manager ID**: Derived from `direct_manager_email`

### Manager Entities
- **Hiring Manager**: Created from `direct_manager_email` and `direct_manager_employee_id`
- **Reporting Manager**: Created from `direct_manager_email` and `direct_manager_employee_id`
- **HRBP**: Created from `hrbp_email_id` and `hrbp_employee_id`
- **Recruiter**: ❌ Not available (not in Darwin API)

---

## Summary

### ✅ What Darwin API Provides:
1. Employee basic info (ID, first name, last name)
2. Direct manager information (95% availability)
3. HRBP information (90% availability)

### ❌ What Darwin API Does NOT Provide:
1. Recruiter information
2. Employee email addresses
3. Job titles/designations
4. Start dates
5. Location/timezone
6. Contact information
7. Address information

---

## Implementation Notes

- The `TalentRecruitClient` uses Darwinbox API as the primary data source
- Recruiter information is no longer available (removed from code)
- Missing fields (email, role, etc.) are generated with defaults
- Manager information is extracted from Darwin API fields
- Field name variations (underscores, spaces, camelCase) are handled

---

## Test Script

Run `test_darwin_api_output.py` to see all available data:
```bash
python test_darwin_api_output.py
```

This will display:
- Statistics about data availability
- Detailed employee information
- All available fields
- Test results with TalentRecruitClient (which wraps Darwinbox API)
