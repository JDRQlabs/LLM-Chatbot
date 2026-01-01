
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Bot, CheckCircle2, MessageSquare, Zap, Globe, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="px-4 lg:px-6 h-14 flex items-center border-b sticky top-0 bg-background/95 backdrop-blur z-50">
        <Link className="flex items-center justify-center font-bold text-xl" href="#">
          <Bot className="h-6 w-6 mr-2 text-primary" />
          Chatbot Platform
        </Link>
        <nav className="ml-auto flex gap-4 sm:gap-6">
          <Link className="text-sm font-medium hover:underline underline-offset-4" href="#features">
            Features
          </Link>
          <Link className="text-sm font-medium hover:underline underline-offset-4" href="#pricing">
            Pricing
          </Link>
          <Link className="text-sm font-medium hover:underline underline-offset-4" href="/auth/login">
            Login
          </Link>
          <Link href="/auth/register">
            <Button size="sm">Get Started</Button>
          </Link>
        </nav>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="w-full py-12 md:py-24 lg:py-32 xl:py-48 bg-gray-50 dark:bg-gray-900 border-b">
          <div className="container px-4 md:px-6">
            <div className="flex flex-col items-center space-y-4 text-center">
              <Badge variant="secondary" className="mb-4">
                Now in Public Beta
              </Badge>
              <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl lg:text-6xl/none bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-violet-600 dark:from-blue-400 dark:to-violet-400 pb-2">
                  Automate WhatsApp with AI Agents
                </h1>
                <p className="mx-auto max-w-[700px] text-gray-500 md:text-xl dark:text-gray-400">
                  Turn comments into leads, automate support, and close sales 24/7 using our intelligent RAG-powered chatbots.
                </p>
              </div>
              <div className="space-x-4">
                <Link href="/auth/register">
                  <Button size="lg" className="h-12 px-8">
                    Start Free Trial <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
                <Link href="#features">
                  <Button variant="outline" size="lg" className="h-12 px-8">
                    View Demo
                  </Button>
                </Link>
              </div>
            </div>
            {/* Hero Image Mock */}
            <div className="mt-12 rounded-xl border bg-background p-2 shadow-2xl mx-auto max-w-5xl overflow-hidden aspect-[16/9] relative">
              <div className="absolute inset-0 bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-900 flex items-center justify-center text-muted-foreground">
                [Dashboard Screenshot Placeholder]
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
                  Key Features
                </div>
                <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl">
                  Everything you need to scale support
                </h2>
                <p className="max-w-[900px] text-gray-500 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed dark:text-gray-400">
                  Our platform combines the power of LLMs with official WhatsApp APIs to deliver a seamless experience.
                </p>
              </div>
            </div>
            <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 mt-12">
              <div className="flex flex-col items-center space-y-2 border rounded-lg p-6 hover:shadow-lg transition-shadow">
                <div className="p-3 rounded-full bg-blue-100 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">
                  <MessageSquare className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-bold">Smart Replies</h3>
                <p className="text-sm text-gray-500 text-center dark:text-gray-400">
                  AI that understands context and intent, not just keywords. Powered by Gemini & OpenAI.
                </p>
              </div>
              <div className="flex flex-col items-center space-y-2 border rounded-lg p-6 hover:shadow-lg transition-shadow">
                <div className="p-3 rounded-full bg-green-100 dark:bg-green-900/20 text-green-600 dark:text-green-400">
                  <Zap className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-bold">Instant Setup</h3>
                <p className="text-sm text-gray-500 text-center dark:text-gray-400">
                  Connect your WhatsApp Business API in minutes. No coding required.
                </p>
              </div>
              <div className="flex flex-col items-center space-y-2 border rounded-lg p-6 hover:shadow-lg transition-shadow">
                <div className="p-3 rounded-full bg-purple-100 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400">
                  <Globe className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-bold">RAG Knowledge Base</h3>
                <p className="text-sm text-gray-500 text-center dark:text-gray-400">
                  Upload PDFs or crawl your website. The bot learns from your data instantly.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Social Proof / Trust */}
        <section className="w-full py-12 md:py-24 lg:py-32 bg-gray-50 dark:bg-gray-900 border-t">
          <div className="container px-4 md:px-6">
            <div className="grid gap-10 sm:px-10 md:gap-16 md:grid-cols-2">
              <div className="space-y-4">
                <div className="inline-block rounded-lg bg-blue-100 px-3 py-1 text-sm dark:bg-blue-900/20 text-blue-600">
                  Testimonials
                </div>
                <h2 className="lg:leading-tighter text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl xl:text-[3.4rem] 2xl:text-[3.75rem]">
                  Trusted by businesses worldwide
                </h2>
                <Link href="/auth/register">
                  <Button className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50">
                    Read Success Stories
                  </Button>
                </Link>
              </div>
              <div className="flex flex-col items-start space-y-4">
                <div className="inline-block rounded-lg bg-background p-4 shadow-sm border">
                  <p className="text-sm text-muted-foreground italic mb-2">
                    "Since switching to this platform, our response time dropped from 4 hours to 4 seconds. Our customers love it!"
                  </p>
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-full bg-gray-200"></div>
                    <div>
                      <p className="text-sm font-semibold">Sarah Mitchell</p>
                      <p className="text-xs text-muted-foreground">CEO, Bloom & Wild</p>
                    </div>
                  </div>
                </div>
                <div className="inline-block rounded-lg bg-background p-4 shadow-sm border">
                  <p className="text-sm text-muted-foreground italic mb-2">
                    "The Lead Capture tool is a game changer. It automatically syncs leads to our CRM, saving us hours of manual entry."
                  </p>
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-full bg-gray-200"></div>
                    <div>
                      <p className="text-sm font-semibold">David Chen</p>
                      <p className="text-xs text-muted-foreground">Marketing Director, TechStart</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="w-full py-12 md:py-24 lg:py-32 bg-primary text-primary-foreground">
          <div className="container px-4 md:px-6 text-center">
            <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl">
              Ready to automate your growth?
            </h2>
            <p className="mx-auto max-w-[600px] text-primary-foreground/80 md:text-xl mt-4 mb-8">
              Join hundreds of businesses using AI to scale their customer support and sales.
            </p>
            <Link href="/auth/register">
              <Button variant="secondary" size="lg" className="h-12 px-8">
                Get Started for Free
              </Button>
            </Link>
            <p className="text-xs mt-4 text-primary-foreground/60">
              No credit card required. 14-day free trial.
            </p>
          </div>
        </section>
      </main>

      <footer className="flex flex-col gap-2 sm:flex-row py-6 w-full shrink-0 items-center px-4 md:px-6 border-t">
        <p className="text-xs text-gray-500 dark:text-gray-400">© 2025 Chatbot Platform. All rights reserved.</p>
        <nav className="sm:ml-auto flex gap-4 sm:gap-6">
          <Link className="text-xs hover:underline underline-offset-4" href="#">
            Terms of Service
          </Link>
          <Link className="text-xs hover:underline underline-offset-4" href="#">
            Privacy
          </Link>
        </nav>
      </footer>
    </div>
  );
}
