# evalshop requirements (fixture)
- FR-1 A customer lists their orders, newest first, 20 per page.
- FR-2 Checkout reserves stock for every line; a line out of stock fails the whole checkout.
- FR-3 Discount (percent) applies to the subtotal BEFORE tax; tax is 10 %.
- NFR-1 Checkout p95 < 500 ms at 50 checkouts/s; flash sales reach 20 writes/s on one SKU.
