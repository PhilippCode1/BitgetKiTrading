import { CustomerPerformanceDetailClient } from "@/components/portal/CustomerPerformanceDetailClient";

export const dynamic = "force-dynamic";

type Props = Readonly<{
  params: Promise<{ id: string }>;
}>;

export default async function CustomerPerformanceDetailPage({ params }: Props) {
  const { id } = await params;
  return <CustomerPerformanceDetailClient periodId={id} />;
}
