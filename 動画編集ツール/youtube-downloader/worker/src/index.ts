import { createRemoteJWKSet, jwtVerify } from 'jose';

export interface Env {
	RENDER_BACKEND_URL: string;
	WORKER_SHARED_SECRET: string;
	CF_ACCESS_TEAM_DOMAIN: string;
	CF_ACCESS_AUD: string;
}

const HEALTH_PATH = '/health';
const ACCESS_EMAIL_HEADER = 'Cf-Access-Authenticated-User-Email';
const ACCESS_JWT_HEADER = 'Cf-Access-Jwt-Assertion';

// バックエンドのレスポンスをそのまま転送すると、Cloudflareの自動decompressで
// Content-Lengthと実body長が食い違い、動画ファイルが壊れることがあるため除外する
const STRIP_RESPONSE_HEADERS = ['content-encoding', 'content-length'];

// createRemoteJWKSetは内部で鍵をキャッシュするため、team domainが変わらない限り使い回す
let cachedJWKS: { teamDomain: string; jwks: ReturnType<typeof createRemoteJWKSet> } | null = null;

function getJWKS(teamDomain: string) {
	if (!cachedJWKS || cachedJWKS.teamDomain !== teamDomain) {
		cachedJWKS = {
			teamDomain,
			jwks: createRemoteJWKSet(new URL(`https://${teamDomain}.cloudflareaccess.com/cdn-cgi/access/certs`)),
		};
	}
	return cachedJWKS.jwks;
}

async function isValidAccessJwt(token: string, env: Env): Promise<boolean> {
	try {
		await jwtVerify(token, getJWKS(env.CF_ACCESS_TEAM_DOMAIN), {
			issuer: `https://${env.CF_ACCESS_TEAM_DOMAIN}.cloudflareaccess.com`,
			audience: env.CF_ACCESS_AUD,
		});
		return true;
	} catch {
		return false;
	}
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);

		if (url.pathname === HEALTH_PATH) {
			return new Response('ok', { status: 200 });
		}

		const userEmail = request.headers.get(ACCESS_EMAIL_HEADER);
		if (!userEmail) {
			return new Response('認証情報が見つかりません（Cloudflare Access経由でアクセスしてください）', { status: 500 });
		}

		// Cf-Access-Authenticated-User-Emailは偽装されうるため、Access発行のJWT署名を検証してから信頼する
		const jwt = request.headers.get(ACCESS_JWT_HEADER);
		if (!jwt || !(await isValidAccessJwt(jwt, env))) {
			return new Response('認証トークンの検証に失敗しました（Cloudflare Access経由でアクセスしてください）', { status: 401 });
		}

		const target = new URL(url.pathname + url.search, env.RENDER_BACKEND_URL);

		const headers = new Headers(request.headers);
		headers.set('X-User-Email', userEmail);
		headers.set('X-Worker-Secret', env.WORKER_SHARED_SECRET);

		const hasBody = request.method !== 'GET' && request.method !== 'HEAD';

		let backendResponse: Response;
		try {
			backendResponse = await fetch(target, {
				method: request.method,
				headers,
				body: hasBody ? request.body : undefined,
				duplex: hasBody ? 'half' : undefined,
				// バックエンドの3xxを自動追従せず、そのままクライアントへ返す
				redirect: 'manual',
			} as RequestInit);
		} catch {
			return new Response(JSON.stringify({ error: 'バックエンドサーバーに接続できませんでした。しばらくしてから再度お試しください。' }), {
				status: 502,
				headers: { 'Content-Type': 'application/json' },
			});
		}

		const responseHeaders = new Headers(backendResponse.headers);
		for (const name of STRIP_RESPONSE_HEADERS) {
			responseHeaders.delete(name);
		}

		return new Response(backendResponse.body, {
			status: backendResponse.status,
			statusText: backendResponse.statusText,
			headers: responseHeaders,
		});
	},
} satisfies ExportedHandler<Env>;
