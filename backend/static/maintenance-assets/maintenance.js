async function checkAvailability() {
    try {
        const health = await fetch('/api/health', { cache: 'no-store', signal: AbortSignal.timeout(5000) });
        if (health.ok) {
            const session = await fetch('/api/auth/me', { cache: 'no-store', credentials: 'same-origin', signal: AbortSignal.timeout(5000) });
            if (session.ok || session.status === 401) {
                window.location.replace('/inbox');
                return;
            }
        }
    } catch (_) {
        // Keep the maintenance page visible while the service is unavailable.
    }
    window.setTimeout(checkAvailability, 5000);
}

window.setTimeout(checkAvailability, 5000);
