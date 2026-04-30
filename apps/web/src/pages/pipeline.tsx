import WorkbenchApp from "@/components/WorkbenchApp";

export default function PipelineRoute() {
  return <WorkbenchApp initialWorkspace="pipeline" />;
}

export async function getServerSideProps() {
  return { props: {} };
}
