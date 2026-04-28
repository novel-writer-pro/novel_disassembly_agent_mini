import WorkbenchApp from "@/components/WorkbenchApp";

export default function ControlRoute() {
  return <WorkbenchApp initialWorkspace="control" />;
}

export async function getServerSideProps() {
  return { props: {} };
}
