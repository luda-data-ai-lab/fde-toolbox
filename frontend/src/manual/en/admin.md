# Customer and user management

These screens are for LUDA admins only: **Customers** and **Users** under **Common** in the left menu.

## Customers

- **Create** a customer with a name and code. Codes must be unique.
- **Archive** finished customers and **Restore** them when needed.
- **Delete** removes all of that customer's data, after a confirmation.

### Moving a customer (ZIP)

- **Export (ZIP)**: downloads all of the customer's data as a ZIP file. Integration credentials are not included.
- **Import ZIP**: enter a **New customer code** and choose a ZIP file to create a new customer from it. IDs are reissued and internal references reconnected.

Use this to move a customer to another installation (for example a server inside the customer) or as a backup.

## Users

1. Enter email, name, role and password (at least 8 characters).
2. Customer admins and customer users need a home customer. FDEs are assigned the customers they work on. LUDA admins can access every customer, so no customer is chosen.
3. Click **Create**. In the list you can change an FDE's assigned customers and switch users between active and inactive.

See [Getting started](/manual/start) for what each role can do.
