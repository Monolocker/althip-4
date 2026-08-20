import type { OutcomeMarket } from "../types/market"

export const fakeMarkets: OutcomeMarket[] = [
    {
        id: "btc-100k",
        question: "Will Bitcoin be above $100,000 at the end of the year?",
        status: "open",
        closesAt: "2026-12-31T23:59:59Z",
        outcomes: [
            {
                side: "YES",
                price: 0.64,
            },
            {
                side: "NO",
                price: 0.36,
            }
        ]
    },
    {
        id: 'eth-5k',
        question: 'Will Ethereum trade above $5,000 before the end of the year?',
        status: 'open',
        closesAt: '2026-12-31T23:59:59Z',
        outcomes: [
          {
            side: 'YES',
            price: 0.41,
          },
          {
            side: 'NO',
            price: 0.59,
          },
        ],
      },
      {
        id: 'sol-300',
        question: 'Will Solana trade above $300 before the end of the year?',
        status: 'open',
        closesAt: '2026-12-31T23:59:59Z',
        outcomes: [
          {
            side: 'YES',
            price: 0.27,
          },
          {
            side: 'NO',
            price: 0.73,
          },
        ],
      },
    ]

