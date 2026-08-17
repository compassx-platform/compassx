a   thn # asset-manager API Surface
Base URL: 

## GET /asset-manager/api/v1/asset-types
Get All Asset Types
Params: id?:string, search?:string, top_level?:string, access_control_type?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-types
Create Asset Types
Body: { name*:string, description?:object, is_active?:boolean, label?:object, access_control_type?:boolean }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/asset-types/{id}
Update Asset Types
Body: { name?:object, description?:object, is_active?:object, label?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/asset-types/{id}
Delete Asset Types
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-types/upload-file
Upload Asset Types
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-types/add-child
Add Child Asset Type Endpoint
Body: { name*:string, description?:object, is_active?:boolean, label?:object, access_control_type?:boolean, hierarchy?:object, parent_asset_type_id*:integer }  (* = required)
Errors: 422:Validation Error

## POST /asset-manager/api/v1/child-assets
Nested Assets
Body: { ancestor_asset_type_ids?:object, ancestor_asset_ids?:object, ancestor_asset_names?:object, asset_type_ids?:object, asset_ids?:object, ancestor_depth?:object, attribute_def_ids?:object, attribute_values?:object, aggregation?:object, search?:object }  (* = required)
Params: page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/child-asset-types
Child Asset Types
Body: { ancestor_asset_type_ids*:array }  (* = required)
Params: page?:integer, size?:integer
Errors: 422:Validation Error

## GET /asset-manager/api/v1/asset-types-hierarchies
Get All Asset Types Hierarchy
Params: id?:string, search?:string, child_asset_type_id?:string, asset_type_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-types-hierarchies
Create Asset Types Hierarchy
Body: { hierarchy_name?:object, asset_type_id*:integer, child_asset_type_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/asset-types-hierarchies/{id}
Update Asset Types Hierarchy
Body: { hierarchy_name?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/asset-types-hierarchies/{id}
Delete Asset Types Hierarchy
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-types-hierarchies/upload-file
Upload Asset Types Hierarchy
Errors: 422:Validation Error

## GET /asset-manager/api/v1/assets
Get All Asset
Params: id?:string, search?:string, top_level?:string, asset_type_id?:string, parent_id?:string, attribute_def_id?:string, attribute_value?:string, manufacturer_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/assets
Create Asset
Body: { name*:string, description?:object, status?:object, unique_asset_identifier*:string, label?:object, is_spare?:boolean, asset_type_id*:integer, manufacturer_id?:object, parent_asset_id?:object }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/assets/{id}
Update Asset
Body: { name*:string, description?:object, status?:object, unique_asset_identifier*:string, label?:object, is_spare?:boolean, manufacturer_id?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/assets/{id}
Delete Asset
Errors: 422:Validation Error

## POST /asset-manager/api/v1/assets/download-template
Download Asset Template
Body: { template_type*:string, asset_type_name*:string, asset_id?:object }  (* = required)
Errors: 422:Validation Error

## POST /asset-manager/api/v1/assets/download-data
Download Data
Body: { template_type*:string, asset_type_name*:string, asset_id?:object }  (* = required)
Errors: 422:Validation Error

## POST /asset-manager/api/v1/assets/upload-file
Upload Asset
Params: asset_type_name*:string, object_type?:string, asset_id?:string
Errors: 422:Validation Error

## POST /asset-manager/api/v1/assets/update-file
Update Asset
Params: asset_type_name*:string, object_type?:string, asset_id?:string
Errors: 422:Validation Error

## POST /asset-manager/api/v1/assets/version-upgrade
Update Version
Body: { root_id*:integer, version*:string, object_type*:string }  (* = required)
Params: asset_type_name*:string, object_type?:string, asset_id?:string
Errors: 422:Validation Error

## POST /asset-manager/api/v1/assets/add-child
Add Child Asset Endpoint
Body: { name*:string, description?:object, status?:object, unique_asset_identifier*:string, label?:object, is_spare?:boolean, asset_type_id*:integer, manufacturer_id?:object, asset_id*:integer, asset_type_hierarchy_id*:integer }  (* = required)
Errors: 422:Validation Error

## POST /asset-manager/api/v1/assets/authorized-assets
Get Authorized Assets
Body: { assets_list?:array }  (* = required)
Errors: 422:Validation Error

## GET /asset-manager/api/v1/asset-hierarchies
Get All Asset Hierarchies
Params: id?:string, search?:string, asset_type_hierarchy_id?:string, asset_id?:string, child_asset_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-hierarchies
Create Asset Hierarchy
Body: { asset_id*:integer, child_asset_id*:integer, asset_type_hierarchy_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/asset-hierarchies/{id}
Update Asset Hierarchy
Body: { updated_by?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/asset-hierarchies/{id}
Delete Asset Hierarchy
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-hierarchies/upload-file
Upload Asset Hierarchy
Errors: 422:Validation Error

## GET /asset-manager/api/v1/locations
Get All Asset Locations
Params: id?:string, search?:string, asset_id?:string, asset_type_id?:string, parent_asset_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/locations
Create Asset Location
Body: { country?:object, state?:object, city?:object, asset_id?:object, latitude?:object, longitude?:object }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/locations/{id}
Update Asset Locations
Body: { country?:object, state?:object, city?:object, latitude?:object, longitude?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/locations/{id}
Delete Asset Locations
Errors: 422:Validation Error

## POST /asset-manager/api/v1/locations/upload-file
Upload Asset Locations
Errors: 422:Validation Error

## GET /asset-manager/api/v1/attribute-definitions
Get All Attribute Definition
Params: id?:string, search?:string, asset_type_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/attribute-definitions
Create Attribute Definition
Body: { name*:string, description?:object, default_value?:object, data_type*:string, uom?:object, asset_type_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/attribute-definitions/{id}
Update Attribute Definition
Body: { name*:string, description?:object, default_value?:object, data_type*:string, uom?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/attribute-definitions/{id}
Delete Attribute Definition
Errors: 422:Validation Error

## POST /asset-manager/api/v1/attribute-definitions/upload-file
Upload Attribute Definition
Errors: 422:Validation Error

## GET /asset-manager/api/v1/asset-attributes
Get All Asset Attributes
Params: id?:string, search?:string, asset_id?:string, attribute_def_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-attributes
Create Asset Attributes
Body: { value*:string, asset_id*:integer, attribute_def_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/asset-attributes/{id}
Update Asset Attributes
Body: { value?:object, created_by?:string, updated_by?:string }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/asset-attributes/{id}
Delete Asset Attributes
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-attributes/upload-file
Upload Asset Attributes
Params: asset_type_name*:string, object_type?:string, asset_id?:string
Errors: 422:Validation Error

## GET /asset-manager/api/v1/tag-definitions
Get All Tag Definitions
Params: id?:string, search?:string, asset_type_id?:string, is_alarm?:string, data_type?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/tag-definitions
Create Tag Definition
Body: { name*:string, description?:object, data_type*:string, asset_type_id*:integer, is_alarm?:object, is_golden?:object, enforce_control?:object, enforce_warnings?:object, lcl?:object, ucl?:object, lwl?:object, uwl?:object, streaming_mode?:object, streaming_frequency?:object, storage?:boolean, retention_days?:object, data_quality?:object }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/tag-definitions/{id}
Update Tag Definition
Body: { name*:string, description?:object, data_type*:string, uom?:object, is_alarm?:object, is_golden?:object, enforce_control?:object, enforce_warnings?:object, lcl?:object, ucl?:object, lwl?:object, uwl?:object, streaming_mode?:object, streaming_frequency?:object, storage?:boolean, retention_days?:object, data_quality?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/tag-definitions/{id}
Delete Tag Definition
Errors: 422:Validation Error

## POST /asset-manager/api/v1/tag-definitions/upload-file
Upload Tag Definition
Params: asset_type_name*:string, object_type?:string, asset_id?:string
Errors: 422:Validation Error

## GET /asset-manager/api/v1/asset-tags
Get All Asset Tags
Params: id?:string, search?:string, asset_id?:string, tag_def_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-tags
Create Asset Tag
Body: { tag*:string, tag_def_id*:integer, asset_id*:integer, lcl?:object, ucl?:object }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/asset-tags/{id}
Update Asset Tag
Body: { tag*:string, uom*:object, is_alarm?:object, lcl*:object, ucl*:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/asset-tags/{id}
Delete Asset Tag
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-tags/upload-file
Upload Asset Tag
Params: asset_type_name*:string, object_type?:string, asset_id?:string
Errors: 422:Validation Error

## GET /asset-manager/api/v1/budget-definitions
Get All Budget Definitions
Params: id?:string, search?:string, asset_type_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/budget-definitions
Create Budget Definition
Body: { name*:string, description?:object, budget_type?:object, uom?:object, asset_type_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/budget-definitions/{id}
Update Budget Definition
Body: { name*:string, description?:object, budget_type?:object, uom?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/budget-definitions/{id}
Delete Budget Definition
Errors: 422:Validation Error

## POST /asset-manager/api/v1/budget-definitions/upload-file
Upload Budget Definition
Errors: 422:Validation Error

## GET /asset-manager/api/v1/asset-budgets
Get Asset Budget
Params: id?:string, search?:string, asset_id?:string, asset_type_id?:string, start_date?:string, end_date?:string, aggregation?:string, budget_def_id?:string, budget_date?:string, budget_granularity?:string
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-budgets
Create Asset Budgets
Body: { value*:number, budget_month*:string, asset_id*:integer, budget_def_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/asset-budgets/{id}
Update Asset Budget
Body: { value*:number, budget_month*:string, updated_by?:string }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/asset-budgets/{id}
Delete Asset Budget
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-budgets/upload-file
Upload Asset Budget
Params: asset_type_name*:string, object_type?:string, asset_id?:string
Errors: 422:Validation Error

## GET /asset-manager/api/v1/alarms
Get All Alarms
Params: id?:string, search?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/alarms
Create Alarms
Body: { alarm_name*:string, description?:object, alarm_type*:string, severity*:string, affected_component?:object, asset_type_id*:integer, alarm_source*:string, availability?:boolean, auto_ticket?:boolean, active_value?:object, deactive_value?:object, activation_window?:integer, n_bit_position?:object, manufacturer_id*:integer, tag_def_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/alarms/{id}
Update Alarms
Body: { alarm_name?:object, description?:object, alarm_type?:object, severity?:object, affected_component?:object, asset_type_id?:object, alarm_source?:object, availability?:object, auto_ticket?:object, active_value?:object, deactive_value?:object, activation_window?:object, n_bit_position?:object, updated_by?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/alarms/{id}
Delete Alarms
Errors: 422:Validation Error

## POST /asset-manager/api/v1/alarms/upload-file
Upload Alarms
Errors: 422:Validation Error

## GET /asset-manager/api/v1/manufacturers
Get All Manufacturers
Params: id?:string, search?:string, asset_type_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/manufacturers
Create Manufacturer
Body: { manufacturer_name*:string, manufacturer_description?:object, model_name?:object, model_type?:object, manufacturer_address?:object, email?:object, fax?:object, phone?:object, n_bit?:object, binary_conversion?:object, additional_properties?:object, asset_type_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/manufacturers/{id}
Update Manufacturer
Body: { manufacturer_name*:string, manufacturer_description?:object, model_name?:object, model_type?:object, manufacturer_address?:object, email?:object, fax?:object, phone?:object, n_bit?:object, binary_conversion?:object, additional_properties?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/manufacturers/{id}
Delete Manufacturer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/manufacturers/upload-file
Upload Manufacturer
Errors: 422:Validation Error

## GET /asset-manager/api/v1/derived-tag-definitions
Get All Tag Definitions
Params: id?:string, search?:string, asset_type_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/derived-tag-definitions
Create Tag Definition
Body: { name*:string, description?:object, data_type*:string, uom?:object, asset_type_id*:integer }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/derived-tag-definitions/{id}
Update Tag Definition
Body: { name*:string, description?:object, data_type?:object, uom?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/derived-tag-definitions/{id}
Delete Tag Definition
Errors: 422:Validation Error

## POST /asset-manager/api/v1/derived-tag-definitions/upload-file
Upload Tag Definition
Errors: 422:Validation Error

## GET /asset-manager/api/v1/asset-paths
Get Asset Paths
Params: id?:string, search?:string, asset_type_id?:string, parent_asset_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-paths
Create Asset Path
Body: { asset_type_id*:integer, parent_asset_id*:integer, path*:array }  (* = required)
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/asset-paths/{id}
Update Asset Path
Body: { path?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/asset-paths/{id}
Delete Asset Path
Errors: 422:Validation Error

## POST /asset-manager/api/v1/asset-paths/upload-file
Upload Asset Path
Params: asset_type_name*:string, object_type?:string, asset_id?:string
Errors: 422:Validation Error

## GET /asset-manager/api/v1/power-curves
Get All Power Curves
Params: id?:string, search?:string, manufacturer_id?:string, type?:string, asset_id?:string, turbine_id?:string, page?:integer, size?:integer
Errors: 422:Validation Error

## POST /asset-manager/api/v1/power-curves
Create Power Curve
Body: { name*:string, description?:object, manufacturer_id?:object, type*:string, asset_id?:object }  (* = required)
Errors: 422:Validation Error

## POST /asset-manager/api/v1/power-curves/upload-file
Create Power Curve With File
Errors: 422:Validation Error

## GET /asset-manager/api/v1/power-curves/{id}
Get Power Curve
Errors: 422:Validation Error

## PUT /asset-manager/api/v1/power-curves/{id}
Update Power Curve
Body: { name?:object, description?:object, manufacturer_id?:object, type?:object, asset_id?:object, data?:object }  (* = required)
Errors: 422:Validation Error

## DELETE /asset-manager/api/v1/power-curves/{id}
Delete Power Curve
Errors: 422:Validation Error

## GET /asset-manager/api/cache/invalidate
Invalidate all cache keys
Errors: 422:Validation Error

## GET /
Read Root

## GET /asset-manager/api/health-check
Health

## GET /healthz
Health
