import WorkbenchApp from "@/components/WorkbenchApp";

export default function QaRoute() {
  return <WorkbenchApp initialWorkspace="qa" />;
}

export async function getServerSideProps() {
  return { props: {} };
}
