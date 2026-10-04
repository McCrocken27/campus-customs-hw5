import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/graduate'
import '@fontsource/oswald/500.css'
import '@fontsource/oswald/700.css'
import '@fontsource/barlow/400.css'
import '@fontsource/barlow/600.css'
import '@fontsource/barlow/700.css'
import './index.css'
import './mascots.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
