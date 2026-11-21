import type { GeneratedImage, Job } from '@/lib/types'

export interface ImageIndex {
  imageById: Map<string, GeneratedImage>
  jobById: Map<string, Job>
  /** Fast image id -> its newest Quality version made with "Render in Quality" */
  qualityOf: Map<string, GeneratedImage>
  /** All images, newest first */
  all: GeneratedImage[]
}

export function buildIndex(jobs: Job[]): ImageIndex {
  const imageById = new Map<string, GeneratedImage>()
  const jobById = new Map<string, Job>()
  const qualityOf = new Map<string, GeneratedImage>()
  const all: GeneratedImage[] = []
  for (const job of jobs) {
    jobById.set(job.id, job)
    for (const img of job.images) {
      imageById.set(img.id, img)
      all.push(img)
    }
  }
  all.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  // oldest first, so the newest Quality version wins
  for (const job of [...jobs].reverse()) {
    if (job.sourceImageId && job.images[0]) qualityOf.set(job.sourceImageId, job.images[0])
  }
  return { imageById, jobById, qualityOf, all }
}
