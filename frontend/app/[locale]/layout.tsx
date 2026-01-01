
import { NextIntlClientProvider } from 'next-intl';
import { getMessages } from 'next-intl/server';
import Providers from "@/components/providers";
import { AuthProvider } from "@/lib/auth-context";
import { Toaster } from "@/components/ui/sonner";
import { Inter } from "next/font/google";
import "@/app/globals.css";

const inter = Inter({ subsets: ["latin"] });

export default async function RootLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: Promise<any>;
}) {
    const messages = await getMessages();
    const { locale } = await params;

    return (
        <html lang={locale}>
            <body className={inter.className}>
                <NextIntlClientProvider messages={messages}>
                    <Providers>
                        <AuthProvider>
                            {children}
                            <Toaster />
                        </AuthProvider>
                    </Providers>
                </NextIntlClientProvider>
            </body>
        </html>
    );
}
