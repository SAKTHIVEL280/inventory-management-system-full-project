"""Pydantic schemas."""

from app.schemas.auth import (
	UserLogin,
	UserResponse,
	TokenResponse,
	RefreshTokenRequest,
	ChangePasswordRequest,
)
from app.schemas.company import CompanyUpdate, CompanyResponse, CompanyLogoResponse
from app.schemas.user import (
	UserCreateRequest,
	UserUpdateRequest,
	UserPermissionsUpdateRequest,
	UserManagementResponse,
	UsersListResponse,
)
from app.schemas.customer import (
	CustomerCreateRequest,
	CustomerUpdateRequest,
	CustomerResponse,
	CustomersListResponse,
	CustomerBalanceResponse,
)
from app.schemas.supplier import (
	SupplierCreateRequest,
	SupplierUpdateRequest,
	SupplierResponse,
	SuppliersListResponse,
	SupplierBalanceResponse,
)
from app.schemas.product import (
	ProductCategoryCreateRequest,
	ProductCategoryResponse,
	UnitOfMeasureResponse,
	ProductCreateRequest,
	ProductUpdateRequest,
	ProductResponse,
	ProductWithStockResponse,
	ProductsListResponse,
)

__all__ = [
	"UserLogin",
	"UserResponse",
	"TokenResponse",
	"RefreshTokenRequest",
	"ChangePasswordRequest",
	"CompanyUpdate",
	"CompanyResponse",
	"CompanyLogoResponse",
	"UserCreateRequest",
	"UserUpdateRequest",
	"UserPermissionsUpdateRequest",
	"UserManagementResponse",
	"UsersListResponse",
	"CustomerCreateRequest",
	"CustomerUpdateRequest",
	"CustomerResponse",
	"CustomersListResponse",
	"CustomerBalanceResponse",
	"SupplierCreateRequest",
	"SupplierUpdateRequest",
	"SupplierResponse",
	"SuppliersListResponse",
	"SupplierBalanceResponse",
	"ProductCategoryCreateRequest",
	"ProductCategoryResponse",
	"UnitOfMeasureResponse",
	"ProductCreateRequest",
	"ProductUpdateRequest",
	"ProductResponse",
	"ProductWithStockResponse",
	"ProductsListResponse",
]

from app.schemas.purchase import (
	PurchaseLineItemRequest,
	PurchaseOrderCreateRequest,
	PurchaseOrderStatusRequest,
	GRNCreateRequest,
	PurchaseReturnLineItemRequest,
	PurchaseReturnCreateRequest,
	PurchaseReturnStatusRequest,
)
from app.schemas.sales import (
	SalesLineItemRequest,
	QuotationCreateRequest,
	QuotationStatusRequest,
	SalesOrderCreateRequest,
	SalesOrderStatusRequest,
	SalesInvoiceCreateRequest,
	SalesReturnLineItemRequest,
	SalesReturnCreateRequest,
)
from app.schemas.payment import (
	PaymentAllocationRequest,
	PaymentCreateRequest,
	PaymentStatusRequest,
)

__all__.extend([
	"PurchaseLineItemRequest",
	"PurchaseOrderCreateRequest",
	"PurchaseOrderStatusRequest",
	"GRNCreateRequest",
	"PurchaseReturnLineItemRequest",
	"PurchaseReturnCreateRequest",
	"PurchaseReturnStatusRequest",
	"SalesLineItemRequest",
	"QuotationCreateRequest",
	"QuotationStatusRequest",
	"SalesOrderCreateRequest",
	"SalesOrderStatusRequest",
	"SalesInvoiceCreateRequest",
	"SalesReturnLineItemRequest",
	"SalesReturnCreateRequest",
	"PaymentAllocationRequest",
	"PaymentCreateRequest",
	"PaymentStatusRequest",
])
