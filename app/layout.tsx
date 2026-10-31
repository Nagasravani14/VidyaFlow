import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Sora } from "next/font/google";
import "./globals.css";
const body = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-body" });
const display = Sora({ subsets: ["latin"], variable: "--font-display" });
export const metadata: Metadata = { title: "VidyaFlow", description: "VidyaFlow — adaptive learning for Classes 6–10 (Telangana State Board & ICSE). Frontend prototype." };
const themeScript = `try{var t=localStorage.getItem('vf-theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme: dark)').matches))document.documentElement.classList.add('dark')}catch(e){}`;
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="en" suppressHydrationWarning className={`${body.variable} ${display.variable}`}>
    <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
    <body className="font-sans">{children}</body></html>);
}
