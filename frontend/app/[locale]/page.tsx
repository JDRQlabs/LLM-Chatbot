
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Bot, MessageSquare, Zap, Globe } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useTranslations } from 'next-intl';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Check } from "lucide-react";

export default function Home() {
    const t = useTranslations();

    return (
        <div className="flex flex-col min-h-screen">
            {/* Header */}
            <header className="px-4 lg:px-6 h-14 flex items-center border-b sticky top-0 bg-background/95 backdrop-blur z-50">
                <Link className="flex items-center justify-center font-bold text-xl" href="#">
                    <Bot className="h-6 w-6 mr-2 text-primary" />
                    Chatbot Platform
                </Link>
                <nav className="ml-auto flex gap-4 sm:gap-6 items-center">
                    <Link className="text-sm font-medium hover:underline underline-offset-4" href="#features">
                        {t('Navigation.features')}
                    </Link>
                    <Link className="text-sm font-medium hover:underline underline-offset-4" href="#pricing">
                        {t('Navigation.pricing')}
                    </Link>
                    <Link className="text-sm font-medium hover:underline underline-offset-4" href="/auth/login">
                        {t('Navigation.login')}
                    </Link>
                    <Link href="/auth/register">
                        <Button size="sm">{t('Navigation.getStarted')}</Button>
                    </Link>
                </nav>
            </header>

            <main className="flex-1">
                {/* Hero Section */}
                <section className="w-full py-12 md:py-24 lg:py-32 xl:py-48 bg-gray-50 dark:bg-gray-900 border-b">
                    <div className="container px-4 md:px-6">
                        <div className="flex flex-col items-center space-y-4 text-center">
                            <Badge variant="secondary" className="mb-4">
                                {t('Hero.badge')}
                            </Badge>
                            <div className="space-y-2">
                                <h1 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl lg:text-6xl/none bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-violet-600 dark:from-blue-400 dark:to-violet-400 pb-2">
                                    {t('Hero.title')}
                                </h1>
                                <p className="mx-auto max-w-[700px] text-gray-500 md:text-xl dark:text-gray-400">
                                    {t('Hero.description')}
                                </p>
                            </div>
                            <div className="space-x-4">
                                <Link href="/auth/register">
                                    <Button size="lg" className="h-12 px-8">
                                        {t('Navigation.startTrial')} <ArrowRight className="ml-2 h-4 w-4" />
                                    </Button>
                                </Link>
                                <Link href="#features">
                                    <Button variant="outline" size="lg" className="h-12 px-8">
                                        {t('Navigation.viewDemo')}
                                    </Button>
                                </Link>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Features Section */}
                <section id="features" className="w-full py-12 md:py-24 lg:py-32 bg-white dark:bg-gray-950">
                    <div className="container px-4 md:px-6">
                        <div className="flex flex-col items-center justify-center space-y-4 text-center">
                            <div className="space-y-2">
                                <div className="inline-block rounded-lg bg-gray-100 px-3 py-1 text-sm dark:bg-gray-800">
                                    {t('Features.tag')}
                                </div>
                                <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl">
                                    {t('Features.title')}
                                </h2>
                                <p className="max-w-[900px] text-gray-500 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed dark:text-gray-400">
                                    {t('Features.subtitle')}
                                </p>
                            </div>
                        </div>
                        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 mt-12">
                            <div className="flex flex-col items-center space-y-2 border rounded-lg p-6 hover:shadow-lg transition-shadow">
                                <div className="p-3 rounded-full bg-blue-100 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">
                                    <MessageSquare className="h-6 w-6" />
                                </div>
                                <h3 className="text-xl font-bold">{t('Features.smartReplies.title')}</h3>
                                <p className="text-sm text-gray-500 text-center dark:text-gray-400">
                                    {t('Features.smartReplies.description')}
                                </p>
                            </div>
                            <div className="flex flex-col items-center space-y-2 border rounded-lg p-6 hover:shadow-lg transition-shadow">
                                <div className="p-3 rounded-full bg-green-100 dark:bg-green-900/20 text-green-600 dark:text-green-400">
                                    <Zap className="h-6 w-6" />
                                </div>
                                <h3 className="text-xl font-bold">{t('Features.instantSetup.title')}</h3>
                                <p className="text-sm text-gray-500 text-center dark:text-gray-400">
                                    {t('Features.instantSetup.description')}
                                </p>
                            </div>
                            <div className="flex flex-col items-center space-y-2 border rounded-lg p-6 hover:shadow-lg transition-shadow">
                                <div className="p-3 rounded-full bg-purple-100 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400">
                                    <Globe className="h-6 w-6" />
                                </div>
                                <h3 className="text-xl font-bold">{t('Features.knowledgeBase.title')}</h3>
                                <p className="text-sm text-gray-500 text-center dark:text-gray-400">
                                    {t('Features.knowledgeBase.description')}
                                </p>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Pricing Section */}
                <section id="pricing" className="w-full py-12 md:py-24 lg:py-32 bg-gray-50 dark:bg-gray-900">
                    <div className="container px-4 md:px-6">
                        <div className="flex flex-col items-center justify-center space-y-4 text-center mb-12">
                            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl">{t('Pricing.title')}</h2>
                            <p className="max-w-[700px] text-gray-500 md:text-xl/relaxed dark:text-gray-400">
                                {t('Pricing.subtitle')}
                            </p>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
                            {['basic', 'professional', 'enterprise'].map((plan) => (
                                <Card key={plan} className={`flex flex-col ${plan === 'professional' ? 'border-primary shadow-lg scale-105' : ''}`}>
                                    <CardHeader>
                                        <CardTitle className="text-2xl">{t(`Pricing.plans.${plan}.name`)}</CardTitle>
                                        <CardDescription>{t(`Pricing.plans.${plan}.description`)}</CardDescription>
                                    </CardHeader>
                                    <CardContent className="flex-1">
                                        <div className="flex items-baseline mb-4">
                                            <span className="text-4xl font-bold">{t(`Pricing.plans.${plan}.price`)}</span>
                                            <span className="text-muted-foreground ml-1">{t(`Pricing.plans.${plan}.period`)}</span>
                                        </div>
                                        <ul className="space-y-2 text-sm">
                                            {[0, 1, 2, 3].map((i) => (
                                                <li key={i} className="flex items-center">
                                                    <Check className="mr-2 h-4 w-4 text-green-500" />
                                                    {t(`Pricing.plans.${plan}.features.${i}`)}
                                                </li>
                                            ))}
                                        </ul>
                                    </CardContent>
                                    <CardFooter>
                                        <Link href="/auth/register" className="w-full">
                                            <Button className="w-full" variant={plan === 'professional' ? 'default' : 'outline'}>
                                                {t(`Pricing.plans.${plan}.cta`)}
                                            </Button>
                                        </Link>
                                    </CardFooter>
                                </Card>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Testimonials */}
                <section className="w-full py-12 md:py-24 lg:py-32 bg-white dark:bg-gray-950 border-t">
                    <div className="container px-4 md:px-6 text-center">
                        <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl mb-8">
                            {t('Testimonials.title')}
                        </h2>
                        <Link href="/auth/register">
                            <Button variant="outline" size="lg">
                                {t('Testimonials.cta')}
                            </Button>
                        </Link>
                    </div>
                </section>

                {/* CTA Section */}
                <section className="w-full py-12 md:py-24 lg:py-32 bg-primary text-primary-foreground">
                    <div className="container px-4 md:px-6 text-center">
                        <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl">
                            {t('CTA.title')}
                        </h2>
                        <p className="mx-auto max-w-[600px] text-primary-foreground/80 md:text-xl mt-4 mb-8">
                            {t('CTA.description')}
                        </p>
                        <Link href="/auth/register">
                            <Button variant="secondary" size="lg" className="h-12 px-8">
                                {t('CTA.button')}
                            </Button>
                        </Link>
                        <p className="text-xs mt-4 text-primary-foreground/60">
                            {t('CTA.note')}
                        </p>
                    </div>
                </section>
            </main>

            <footer className="flex flex-col gap-2 sm:flex-row py-6 w-full shrink-0 items-center px-4 md:px-6 border-t">
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('Footer.copyright')}</p>
                <nav className="sm:ml-auto flex gap-4 sm:gap-6">
                    <Link className="text-xs hover:underline underline-offset-4" href="#">
                        {t('Footer.terms')}
                    </Link>
                    <Link className="text-xs hover:underline underline-offset-4" href="#">
                        {t('Footer.privacy')}
                    </Link>
                </nav>
            </footer>
        </div>
    );
}
