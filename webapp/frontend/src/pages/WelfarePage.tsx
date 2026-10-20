import WelfareList from "../components/WelfareList";
import { PageHeader } from "../components/ui";

export default function WelfarePage() {
  return (
    <>
      <PageHeader title="Welfare checks" subtitle="Who still needs a check today, what happened, and who needs a follow-up. Each area's page shows the seniors who live there." />
      <WelfareList />
    </>
  );
}
