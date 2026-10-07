import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { PersonaProvider } from './state/persona'; // Stage Y: demo persona switch + X-Persona on /api/*
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PersonaProvider>
      <App />
    </PersonaProvider>
  </React.StrictMode>
);
