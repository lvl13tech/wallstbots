-- Add Stripe subscription ID column to subscriptions table
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS origin_platform VARCHAR(50);
