import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'

// One cache for the whole app. Created once, outside any component, 
// so re-renders never replace it 

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The backend already absorbs upstream failures; one retry covers
      // a transient blip w/o delaying a real error for long 
      retry: 1
    }
  }
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
