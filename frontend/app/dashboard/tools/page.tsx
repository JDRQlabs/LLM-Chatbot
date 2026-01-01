
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

export default function ToolsPage() {
    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold tracking-tight">Tools & Integrations</h1>

            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex justify-between items-center">
                            Pricing Calculator
                            <Switch defaultChecked />
                        </CardTitle>
                        <CardDescription>Automatically calculate quotes based on volume.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-sm text-muted-foreground mb-4">
                            Uses the internal pricing engine to deliver instant quotes via WhatsApp.
                        </div>
                        <Button variant="outline" className="w-full">Configure</Button>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="flex justify-between items-center">
                            Lead Capture
                            <Switch defaultChecked />
                        </CardTitle>
                        <CardDescription>Save contact details to CRM.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-sm text-muted-foreground mb-4">
                            Extracts name, email, and company from conversation and saves to Leads table.
                        </div>
                        <Button variant="outline" className="w-full">Configure</Button>
                    </CardContent>
                </Card>

                <Card className="opacity-60">
                    <CardHeader>
                        <CardTitle className="flex justify-between items-center">
                            Google Calendar
                            <Switch disabled />
                        </CardTitle>
                        <CardDescription>Coming Soon</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-sm text-muted-foreground mb-4">
                            Allow users to book meetings directly through WhatsApp.
                        </div>
                        <Button variant="outline" disabled className="w-full">Configure</Button>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
