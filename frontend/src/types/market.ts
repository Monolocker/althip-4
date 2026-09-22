export interface OutcomeSide {
    index: number
    label: string
    coin: string
    price: number | null
}

export interface OutcomeMarket {
    id: string
    name: string
    question: string
    description: string
    status: "open" | "settled"
    closesAt: string | null
    quoteToken: string
    venue: string
    sides: OutcomeSide[]
}
