# S_sec rubric (D-10)

For each event type, choose `SECURITY` or `NOT_SECURITY`.

`SECURITY` if **either**:
- a frozen rule consumes the type (`security_basis` would be `rule_dependency`), or
- it is audit evidence of auth failure, permission/sharing change, bulk export, denied
  access, rate-limit, or webhook/config change (`audit_category`).

Otherwise `NOT_SECURITY`.

Do not open `annotator_a.yaml`. Do not change the catalog until both raters agree or
an adjudication note exists.
