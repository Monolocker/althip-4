// Browser wallets, read-only (Milestone 27.2). Two standards, no library:
//   EIP-1193: the provider object a wallet injects into the page. Every
//     call is one JSON-RPC request; changes arrive as events.
//   EIP-6963: how a page discovers EVERY installed wallet. The older
//     window.ethereum holds whichever extension injected itself last, so
//     with Rabby and MetaMask both installed you cannot choose.

export interface Eip1193Provider {
    request(args: { method: string; params?: unknown[] }): Promise<unknown>
    on?(event: string, listener: (...args: unknown[]) => void): void
    removeListener?(event: string, listener: (...args: unknown[]) => void): void
  }
  
  // What a wallet announces about itself. rdns is a stable id (reverse
  // domain, e.g. "io.rabby"); uuid changes on every page load.
  export interface WalletInfo {
    uuid: string
    name: string
    icon: string
    rdns: string
  }
  
  export interface WalletDetail {
    info: WalletInfo
    provider: Eip1193Provider
  }
  
  const ADDRESS = /^0x[0-9a-fA-F]{40}$/
  // An icon is shown only as a data: image. An <img> never runs scripts,
  // even from an SVG, and a data: URL makes no network request.
  const SAFE_ICON = /^data:image\/(svg\+xml|png|jpeg|webp|gif)[;,]/
  
  function isWalletDetail(value: unknown): value is WalletDetail {
    if (typeof value !== 'object' || value === null) {
      return false
    }
    const { info, provider } = value as { info?: Partial<WalletInfo>; provider?: Partial<Eip1193Provider> }
    return (
      typeof info?.uuid === 'string' &&
      typeof info.name === 'string' &&
      typeof info.rdns === 'string' &&
      typeof provider?.request === 'function'
    )
  }
  
  // Listens for wallets announcing themselves, then asks all of them to
  // announce. Wallets that load later announce on their own. Returns the
  // cleanup that stops listening.
  export function discoverWallets(onAnnounce: (wallet: WalletDetail) => void): () => void {
    function handleAnnounce(event: Event) {
      const detail: unknown = (event as CustomEvent).detail
      if (isWalletDetail(detail)) {
        onAnnounce(detail)
      }
    }
    window.addEventListener('eip6963:announceProvider', handleAnnounce)
    window.dispatchEvent(new Event('eip6963:requestProvider'))
    return () => window.removeEventListener('eip6963:announceProvider', handleAnnounce)
  }
  
  export function safeIcon(icon: string): string | null {
    return SAFE_ICON.test(icon) ? icon : null
  }
  
  // eth_accounts / eth_requestAccounts answer with a list of addresses;
  // anything malformed is dropped. Lowercased, as Hyperliquid recommends
  // for every address it is sent.
  export function parseAccounts(value: unknown): string[] {
    if (!Array.isArray(value)) {
      return []
    }
    return value
      .filter((item): item is string => typeof item === 'string' && ADDRESS.test(item))
      .map((address) => address.toLowerCase())
  }
  
  // eth_chainId answers in hex, e.g. "0xa4b1" (42161, Arbitrum One).
  export function parseChainId(value: unknown): number | null {
    if (typeof value !== 'string' || !/^0x[0-9a-fA-F]+$/.test(value)) {
      return null
    }
    return Number.parseInt(value, 16)
  }
  
  // EIP-1193 errors carry a numeric code; the common ones get plain words.
  export function walletErrorMessage(error: unknown): string {
    const { code, message } = (error ?? {}) as { code?: unknown; message?: unknown }
    if (code === 4001) {
      return 'The request was rejected in your wallet.'
    }
    if (code === -32002) {
      return 'Your wallet already has a request open. Check its window.'
    }
    return typeof message === 'string' && message !== '' ? message : 'The wallet request failed.'
  }