# RetailCo Order Fulfilment Refactoring Specification

## Original problem

`OrderManager` is a God Class. It mixes order lifecycle management, inventory operations, payment integration, shipment management, customer notification, and analytics/event publishing. This makes the class difficult to test, difficult to change safely, and likely to accumulate more unrelated responsibilities over time.

## Extracted units

### OrderRepository

`OrderRepository` owns order storage and order ID generation. It was extracted because persistence/lifecycle storage is independent of fulfilment rules and should not require changes to payment, shipping, or notification code.

### InventoryService

`InventoryService` owns stock availability, reservation, and delivery accounting. Keeping inventory rules together gives the inventory responsibility a single home and makes it independently testable.

### PaymentService + PaymentGateway

`PaymentService` coordinates payment authorization while `PaymentGateway` defines the integration boundary. The concrete `CardPaymentGateway` contains card-specific behavior, so the application does not depend directly on a particular payment provider.

### ShipmentService

`ShipmentService` owns shipment creation and delivery status. This isolates fulfilment-centre/shipping state changes from the rest of the order workflow.

### Notifier

`Notifier` owns customer-facing shipping notifications. Notification formatting and delivery-channel concerns can therefore change without modifying order, payment, or inventory logic.

### AnalyticsPublisher

`AnalyticsPublisher` owns analytics/event emission. The order workflow only tells it which event occurred; it does not need to know how analytics events are stored or published.

### OrderService

`OrderService` is the application-level orchestrator. It uses composition to coordinate the focused collaborators instead of implementing all their responsibilities itself. Its job is workflow coordination, not payment, inventory, persistence, notification, shipment, or analytics implementation.

## Design principles applied

The refactoring primarily applies the Single Responsibility Principle and composition over inheritance. The original God Class is decomposed into cohesive units with explicit dependencies.

The payment boundary also applies the Open/Closed Principle: `PaymentService` depends on the `PaymentGateway` protocol, so a new payment method can implement the gateway contract without changing `PaymentService` or `OrderService`.

## Testing

Existing business scenarios are represented by pytest tests covering order creation, inventory reservation, payment authorization/rejection, shipment creation, notification, analytics, the complete fulfilment flow, and back-order handling. Each extracted unit has at least one focused test.

## Suggested exercise

For learners, first inspect `god_class_starter.py` and list responsibilities before opening `order_fulfilment.py`. Then compare the solution against the responsibility map and explain why composition makes each dependency replaceable.
