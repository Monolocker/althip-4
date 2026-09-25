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

export interface QuestionMembership {
    questionId: string
    name: string
    description: string
    isFallback: boolean
    siblingIds: string[]
}

export interface Settlement {
    settleFraction: number | null
    details: string
    winningSideIndex: number | null
  }
  
  export interface OutcomeMarketDetail extends OutcomeMarket {
    spec: Record<string, string>
    deployer: string | null
    questionGroup: QuestionMembership | null
    settlement: Settlement | null
  }