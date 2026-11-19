import { useCallback, useEffect, useRef, useState } from 'react'
import {
  discoverWallets,
  parseAccounts,
  parseChainId,
  walletErrorMessage,
  type WalletDetail,
  type WalletInfo,
} from './eip1193'

export type WalletStatus = 'disconnected' | 'connecting' | 'connected'

export interface WalletState {
  wallets: WalletInfo[]  // every wallet that announced itself
  status: WalletStatus
  wallet: WalletInfo | null  // the connected wallet
  address: string | null  // lowercased
  chainId: number | null  // kept for 27.4: approveAgent names the chain
  error: string | null
  connect: (uuid: string) => void
  disconnect: () => void
}

// Remembers WHICH wallet was used (its rdns), never anything secret, so
// a reload can reconnect without a popup.
const STORAGE_KEY = 'cross.wallet.rdns'

function readRemembered(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null  // storage can be blocked; reconnecting is a convenience
  }
}

function writeRemembered(rdns: string | null) {
  try {
    if (rdns === null) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, rdns)
    }
  } catch {
    // Same as above: without storage, the next visit asks again.
  }
}

export function useWallet(): WalletState {
  const [details, setDetails] = useState<WalletDetail[]>([])
  const [active, setActive] = useState<WalletDetail | null>(null)
  const [status, setStatus] = useState<WalletStatus>('disconnected')
  const [address, setAddress] = useState<string | null>(null)
  const [chainId, setChainId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Every connect or disconnect bumps this. A wallet answer that arrives
  // after a newer attempt (or a disconnect) is stale and is ignored.
  const attempt = useRef(0)
  const triedSilent = useRef(false)

  useEffect(() => discoverWallets((detail) => {
    setDetails((current) =>
      current.some((known) => known.info.uuid === detail.info.uuid) ? current : [...current, detail],
    )
  }), [])

  const finish = useCallback((detail: WalletDetail, accounts: string[], chain: number | null) => {
    setActive(detail)
    setAddress(accounts[0])
    setChainId(chain)
    setStatus('connected')
    setError(null)
    writeRemembered(detail.info.rdns)
  }, [])

  // Reconnect after a reload: eth_accounts never opens a popup. It lists
  // accounts only if this site was already approved in that wallet.
  useEffect(() => {
    const remembered = readRemembered()
    const detail = details.find((known) => known.info.rdns === remembered)
    if (triedSilent.current || detail === undefined) {
      return
    }
    triedSilent.current = true
    const current = ++attempt.current
    void (async () => {
      try {
        const accounts = parseAccounts(await detail.provider.request({ method: 'eth_accounts' }))
        const chain = parseChainId(await detail.provider.request({ method: 'eth_chainId' }))
        if (current === attempt.current && accounts.length > 0) {
          finish(detail, accounts, chain)
        }
      } catch {
        // A silent check that fails just leaves the Connect button.
      }
    })()
  }, [details, finish])

  const connect = useCallback((uuid: string) => {
    const detail = details.find((known) => known.info.uuid === uuid)
    if (detail === undefined) {
      return
    }
    const current = ++attempt.current
    setStatus('connecting')
    setError(null)
    void (async () => {
      try {
        // Opens the wallet's "connect to this site?" prompt. Only shares
        // the public address: nothing is signed.
        const accounts = parseAccounts(await detail.provider.request({ method: 'eth_requestAccounts' }))
        const chain = parseChainId(await detail.provider.request({ method: 'eth_chainId' }))
        if (current !== attempt.current) {
          return
        }
        if (accounts.length === 0) {
          setStatus('disconnected')
          setError('The wallet shared no account.')
          return
        }
        finish(detail, accounts, chain)
      } catch (exc) {
        if (current === attempt.current) {
          setStatus('disconnected')
          setError(walletErrorMessage(exc))
        }
      }
    })()
  }, [details, finish])

  // Forgets the wallet in this app. The wallet itself still lists the
  // site as connected until it is removed in the wallet's settings.
  const disconnect = useCallback(() => {
    attempt.current += 1
    setActive(null)
    setAddress(null)
    setChainId(null)
    setStatus('disconnected')
    setError(null)
    writeRemembered(null)
  }, [])

  // Follow the wallet: switching account or chain there updates here.
  useEffect(() => {
    const provider = active?.provider
    if (provider === undefined || provider.on === undefined) {
      return
    }
    function handleAccounts(value: unknown) {
      const accounts = parseAccounts(value)
      if (accounts.length === 0) {
        disconnect()  // the user disconnected this site in the wallet
      } else {
        setAddress(accounts[0])
      }
    }
    function handleChain(value: unknown) {
      setChainId(parseChainId(value))
    }
    provider.on('accountsChanged', handleAccounts)
    provider.on('chainChanged', handleChain)
    return () => {
      provider.removeListener?.('accountsChanged', handleAccounts)
      provider.removeListener?.('chainChanged', handleChain)
    }
  }, [active, disconnect])

  return {
    wallets: details.map((detail) => detail.info),
    status,
    wallet: active?.info ?? null,
    address,
    chainId,
    error,
    connect,
    disconnect,
  }
}