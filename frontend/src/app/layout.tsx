import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { LanguageProvider, type Locale } from "@/contexts/LanguageContext";
import { cookies } from "next/headers";
import Sidebar from "@/components/Sidebar";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
});

export const metadata: Metadata = {
  title: "AI Video Factory",
  description: "Generate viral vertical micro-dramas with AI",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get("locale")?.value;
  const initialLocale: Locale = cookieLocale === "en" || cookieLocale === "ru" ? cookieLocale : "ru";

  return (
    <html lang={initialLocale} className="dark" suppressHydrationWarning>
      <body className={`${inter.className} bg-gray-900 text-white antialiased`}>
        <LanguageProvider initialLocale={initialLocale}>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 min-w-0">
              {children}
            </main>
          </div>
        </LanguageProvider>
      </body>
    </html>
  );
}
