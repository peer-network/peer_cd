<?php

// Only allow POST requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo 'Method Not Allowed';
    exit;
}

// Load the GitHub webhook secret from the environment
$secret = getenv('DEPLOY_WEBHOOK_SECRET');
if (!$secret) {
    http_response_code(500);
    echo 'Server misconfigured: missing webhook secret';
    exit;
}

// Validate GitHub signature
$headers = getallheaders();
$hubSignature = $headers['X-Hub-Signature-256'] ?? '';
$payloadRaw = file_get_contents('php://input');
$hash = 'sha256=' . hash_hmac('sha256', $payloadRaw, $secret);

if (!hash_equals($hash, $hubSignature)) {
    http_response_code(403);
    echo 'Invalid signature';
    exit;
}

// Decode JSON payload
$payload = json_decode($payloadRaw, true);

// Trigger only on merged PRs into development
if (
    isset($payload['action'], $payload['pull_request']) &&
    $payload['action'] === 'closed' &&
    $payload['pull_request']['merged'] === true &&
    $payload['pull_request']['base']['ref'] === 'development'
) {
    file_put_contents('/var/log/webhook.log', "[" . date('Y-m-d H:i:s') . "] PR merged into development – Deploy triggered\n", FILE_APPEND);
    shell_exec('/home/ubuntu/deploy-scripts/deploy-backend.sh >> /var/log/deploy.log 2>&1 &');
    http_response_code(200);
    echo 'Deployment triggered from PR merge to development';
    exit;
} else {
    file_put_contents('/var/log/webhook.log', "[" . date('Y-m-d H:i:s') . "] Webhook ignored – not a merged PR to development\n", FILE_APPEND);
    http_response_code(200);
    echo 'No deployment triggered';
    exit;
}

