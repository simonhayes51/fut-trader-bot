# FC27 Premium Billing Setup

The community platform includes a first-party Stripe subscription and Discord entitlement system.

## 1. Required environment variables

```env
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
BILLING_CURRENCY=gbp
BASE_URL=https://your-dashboard-domain.example
```

Keep Stripe secrets in Railway/environment secrets. Never commit them.

## 2. Stripe products and prices

Create recurring Stripe Prices for each membership tier (for example monthly and annual Premium). Copy each `price_...` ID into **FC27 Control → Premium & billing → Membership plans** and map it to the Discord role that should be granted.

The dashboard can configure:
- plan name and slug
- Stripe Price ID
- Discord entitlement role
- free-trial days
- active/disabled state
- display order

Stripe remains responsible for card collection, invoices, retries and payment-method storage. The bot never handles raw card data.

## 3. Stripe webhook

Create a Stripe webhook endpoint pointing to:

`https://YOUR_BASE_URL/billing/webhook`

Subscribe to at least:
- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`
- `charge.dispute.created`

Copy the endpoint signing secret (`whsec_...`) into `STRIPE_WEBHOOK_SECRET`.

Webhook events are signature-verified and stored by event ID before processing so retries are idempotent.

## 4. Discord commands

- `/premium` lists active plans.
- `/premium plan:premium` creates a private Stripe Checkout link tied to the Discord user.
- `/premium plan:premium referral:CODE` attributes the checkout to a referral code.
- `/subscription` shows membership status and creates a private Stripe Billing Portal link when a Stripe customer exists.

## 5. Entitlements and role sync

Stripe subscription states are converted into internal entitlements. Active, trialing and past-due subscriptions retain access by default. Canceled/unpaid/expired subscriptions revoke the mapped role.

Manual complimentary access uses the same entitlement layer, so staff can grant a user Premium for a defined number of days without creating a fake Stripe payment.

## 6. Referral tracking

Referral codes can be created in the billing dashboard and optionally attached to a Discord user. The system tracks checkout starts and completed conversions. Reward type/value are stored for reporting and future automated payout/credit logic; no cash payout is performed automatically.

## 7. Testing before live payments

Use Stripe test mode first. Verify:
1. successful checkout adds the Discord role;
2. trialing subscription adds the role;
3. cancellation/deletion removes the role;
4. payment failure is visible in audit/billing events;
5. `/subscription` opens the Stripe customer portal;
6. duplicate webhook delivery does not duplicate entitlements;
7. a manual comp expires/revokes correctly.

Only switch to live keys after the test flow is confirmed end to end.
