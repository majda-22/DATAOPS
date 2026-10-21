# Source contracts and referential checks

The catalog contains the seven core Olist tables (orders plus customers, items,
payments, reviews, products, sellers) and UCI Online Retail. Geolocation and the
category translation lookup are auxiliary source files outside this core scope.
Postal-code prefixes are not unique geolocation keys, so no false zip-code FK is
declared. Source headers, including Olist's `lenght` spelling, are preserved.

Orders reference customers. Order items reference orders, products, and sellers.
Payments and reviews reference orders. Review identity is `(review_id, order_id)`:
`review_id` alone is not unique in the local source. Optional review text and
product descriptive/dimension fields remain nullable. Contracts are Bronze
expectations; source violations are reported, never silently cleaned away.

Use `load_catalog()` to validate every reference resolves to a declared unique
key. `evaluate_csv(..., reference_data={dataset: csv_path})` enforces relationships,
including composite keys. Missing reference inputs and non-unique parent keys
raise errors rather than skipping checks. A null key component uses SQL MATCH
SIMPLE semantics; non-nullable source columns are checked independently.

All source contracts require at least one row. Volume failure is dataset-level,
so its failed_rows is zero and its evidence contains required/observed counts.
Generated integrity IDs get deterministic suffixes if an explicit ID uses the
same name. Duplicate source or reference headers are rejected.

The [UCI source](https://archive.ics.uci.edu/dataset/352/online+retail) is an XLSX
workbook. The contract targets a CSV export retaining InvoiceNo, StockCode,
Description, Quantity, InvoiceDate, UnitPrice, CustomerID, and Country. Preserve
returns/cancellations, allow nullable Description/CustomerID, and do not infer a
unique transaction-line key from invoice/product identifiers. A keyless contract
must provide keyless_reason; source hash plus row ordinal identifies raw records.
Logical-type enforcement and XLSX conversion are deferred; export timestamps
as ISO 8601 for timestamp profiling. No UCI rows or detector results are claimed
by the Olist verification. Attribution: Chen, D. (2015), Online Retail, UCI,
DOI 10.24432/C5BW33, CC BY 4.0.
