import type { Metadata } from 'next';
import './globals.css';
import './coach.css';
import './review.css';
export const metadata:Metadata={title:'Djoker — Serve review',description:'Upload a serve, track your movement, and review the evidence.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>;}
