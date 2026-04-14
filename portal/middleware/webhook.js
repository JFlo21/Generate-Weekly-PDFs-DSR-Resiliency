/**
 * Webhook Signature Validation Middleware
 *
 * Validates GitHub webhook deliveries using the X-Hub-Signature-256 HMAC header.
 * Prevents forged payloads from being processed by webhook endpoints.
 *
 * Created in response to GitHub security notification GH-9951654-7992-a1
 * regarding webhook secret exposure (September-December 2025).
 *
 * Usage:
 *   const express = require('express');
 *   const { verifyWebhookSignature } = require('./middleware/webhook');
 *
 *   // IMPORTANT: Use express.raw(), NOT express.json(), on the webhook route.
 *   // The raw body bytes are required for HMAC computation.
 *   app.post('/webhook',
 *     express.raw({ type: 'application/json' }),
 *     verifyWebhookSignature,
 *     (req, res) => {
 *       const event = req.headers['x-github-event'];
 *       const payload = req.webhookPayload;
 *       // handle event...
 *       res.status(200).json({ received: true });
 *     }
 *   );
 */

'use strict';

const crypto = require('node:crypto');

/**
 * Express middleware that validates the X-Hub-Signature-256 HMAC signature
 * on incoming GitHub webhook payloads.
 *
 * Requires:
 * - WEBHOOK_SECRET environment variable to be set
 * - req.body to be a raw Buffer (use express.raw(), not express.json())
 */
function verifyWebhookSignature(req, res, next) {
  const secret = process.env.WEBHOOK_SECRET;
  if (!secret) {
    console.error('WEBHOOK_SECRET environment variable is not configured');
    return res.status(500).json({ error: 'Webhook not configured' });
  }

  const signatureHeader = req.headers['x-hub-signature-256'];
  if (!signatureHeader) {
    return res.status(401).json({ error: 'Missing X-Hub-Signature-256 header' });
  }

  // Express can return an array for duplicate headers; reject that case
  if (Array.isArray(signatureHeader)) {
    return res.status(401).json({ error: 'Invalid X-Hub-Signature-256 header' });
  }

  const signature = signatureHeader;

  if (!Buffer.isBuffer(req.body)) {
    console.error('Webhook route must use express.raw(), not express.json()');
    return res.status(500).json({ error: 'Server misconfiguration' });
  }

  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(req.body)
    .digest('hex');

  // timingSafeEqual requires equal-length buffers; reject if lengths differ
  const sigBuffer = Buffer.from(signature, 'utf8');
  const expectedBuffer = Buffer.from(expected, 'utf8');

  if (sigBuffer.length !== expectedBuffer.length ||
      !crypto.timingSafeEqual(sigBuffer, expectedBuffer)) {
    return res.status(401).json({ error: 'Invalid webhook signature' });
  }

  // Parse the raw body into JSON for downstream handlers
  try {
    req.webhookPayload = JSON.parse(req.body.toString('utf8'));
  } catch {
    return res.status(400).json({ error: 'Invalid JSON payload' });
  }

  next();
}

module.exports = { verifyWebhookSignature };
