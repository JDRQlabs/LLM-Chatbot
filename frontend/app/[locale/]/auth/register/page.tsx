
"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Bot, CheckCircle2 } from "lucide-react";
import { useTranslations } from 'next-intl';

export default function Register() {
    const [email, setEmail] = useState("");
    const [isSubmitted, setIsSubmitted] = useState(false);
    const t = useTranslations('Auth.waitlist');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        // In a real app, send to API here
        console.log("Waitlist email:", email);
        setIsSubmitted(true);
    };

    if (isSubmitted) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900 p-4">
                <Card className="w-full max-w-md text-center">
                    <CardHeader>
                        <div className="flex justify-center mb-4">
                            <CheckCircle2 className="h-12 w-12 text-green-500" />
                        </div>
                        <CardTitle className="text-2xl">{t('successTitle')}</CardTitle>
                        <CardDescription>
                            {t('successMessage')}
                        </CardDescription>
                    </CardHeader>
                    <CardFooter className="justify-center">
                        <Link href="/">
                            <Button variant="outline">{t('backToHome')}</Button>
                        </Link>
                    </CardFooter>
                </Card>
            </div>
        );
    }

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 dark:bg-gray-900 p-4">
            <Link href="/" className="mb-8 flex items-center gap-2 text-lg font-bold">
                <Bot className="h-6 w-6 text-primary" />
                Chatbot Platform
            </Link>

            <Card className="w-full max-w-md">
                <CardHeader className="space-y-1">
                    <CardTitle className="text-2xl text-center">{t('title')}</CardTitle>
                    <CardDescription className="text-center">
                        {t('subtitle')}
                    </CardDescription>
                </CardHeader>
                <form onSubmit={handleSubmit}>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Input
                                id="email"
                                type="email"
                                placeholder={t('email')}
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                            />
                        </div>
                    </CardContent>
                    <CardFooter>
                        <Button className="w-full" type="submit">
                            {t('submit')}
                        </Button>
                    </CardFooter>
                </form>
            </Card>
        </div>
    );
}
