import WorkbenchApp from "@/components/WorkbenchApp";

export default function OpsRoute() {
  return <WorkbenchApp initialWorkspace="ops" />;
}

export async function getServerSideProps() {
  return { props: {} };
}
