export type OutcomeSide = "YES" | "NO"

export interface MarketOutcome {
    side: OutcomeSide
    price: number
}

export interface OutcomeMarket {
    id: string
    question: string
    status: "open" | "closed"
    closesAt: string
    outcomes: MarketOutcome[]
}