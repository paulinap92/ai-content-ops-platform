# Social workspace and private database browser

The standalone Content Editor runs on Render behind its existing login. Public website services are separate.

## Social workflow

- Create and edit a post for Instagram, Facebook and/or WhatsApp.
- Shared Spanish copy can have a separate version for each channel.
- Choose an image from the existing unified Drive/upload library. A chosen Drive image is copied into the durable website media library; its original remains on Drive.
- Save drafts, approve a material, and view per-channel content previews.
- Instagram approval requires an image and a caption no longer than 2200 characters.
- Copy text, download the image, and open Metricool for Instagram/Facebook. The editor does not transfer a post to Metricool automatically.
- WhatsApp opens a pre-filled message. Device sharing can include text and an image when the browser supports file sharing. The owner selects the recipient and sends it. WhatsApp Channel publication remains a manual action in WhatsApp.
- Opening a destination or sharing a file never marks a post published. The owner explicitly confirms each channel after publication. History retains that channel's original copy and image.
- Archived drafts can be restored. Edits return approval to draft. Concurrent writes are rejected using a version check.

## Storage and delivery

All social drafts and history stay in the editor's private `social_drafts` collection (PostgreSQL in hosted deployment, MongoDB for existing installations). Existing drafts remain readable, with stable IDs and complete saved text. No public canonical content or provider posts are modified by this workflow.

Metricool currently has the brand `canarias.cerca` with Instagram and Facebook connected (verified 4 November 2026 through the connected account). The editor uses manual handoff; its API reports `publishing_connected=false`. An independent server integration would require owner-provided server credentials and a Metricool plan with API access. No social secrets are stored in browser assets, and this change adds no paid service.

## Validation

CI runs the workflow against disposable PostgreSQL and MongoDB stores, checks authentication, conflicting edits, image requirements, archival and retained publication snapshots. Browser tests cover choosing a library image without losing the draft, channel previews, WhatsApp pre-filled text, manual confirmation, and phone layout. These tests never send or schedule an external message.
