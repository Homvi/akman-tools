import { redirect } from "@/i18n/routing";
import { routing } from "@/i18n/routing";

export default function RootPage() {
  redirect({ href: "/dashboard", locale: routing.defaultLocale });
}
