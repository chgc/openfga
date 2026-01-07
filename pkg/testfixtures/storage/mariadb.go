package storage

import (
	"context"
	"io"
	"log"
	"strings"
	"testing"
	"time"

	"github.com/cenkalti/backoff/v4"
	"github.com/containerd/errdefs"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/client"
	"github.com/docker/go-connections/nat"
	"github.com/go-sql-driver/mysql"
	"github.com/oklog/ulid/v2"
	"github.com/pressly/goose/v3"
	"github.com/stretchr/testify/require"

	"github.com/openfga/openfga/assets"
)

const (
	mariaDBImage = "mariadb:11"
)

type mariaDBTestContainer struct {
	addr     string
	version  int64
	username string
	password string
}

// NewMariaDBTestContainer returns an implementation of the DatastoreTestContainer interface
// for MariaDB.
func NewMariaDBTestContainer() *mariaDBTestContainer {
	return &mariaDBTestContainer{}
}

func (m *mariaDBTestContainer) GetDatabaseSchemaVersion() int64 {
	return m.version
}

// RunMariaDBTestContainer runs a MariaDB container, connects to it, and returns a
// bootstrapped implementation of the DatastoreTestContainer interface wired up for the
// MariaDB datastore engine.
func (m *mariaDBTestContainer) RunMariaDBTestContainer(t testing.TB) DatastoreTestContainer {
	dockerClient, err := client.NewClientWithOpts(
		client.FromEnv,
		client.WithAPIVersionNegotiation(),
	)
	require.NoError(t, err)
	t.Cleanup(func() {
		dockerClient.Close()
	})

	allImages, err := dockerClient.ImageList(context.Background(), image.ListOptions{
		All: true,
	})
	require.NoError(t, err)

	foundMariaDBImage := false

AllImages:
	for _, image := range allImages {
		for _, tag := range image.RepoTags {
			if strings.Contains(tag, mariaDBImage) {
				foundMariaDBImage = true
				break AllImages
			}
		}
	}

	if !foundMariaDBImage {
		t.Logf("Pulling image %s", mariaDBImage)
		reader, err := dockerClient.ImagePull(context.Background(), mariaDBImage, image.PullOptions{})
		require.NoError(t, err)

		_, err = io.Copy(io.Discard, reader)
		require.NoError(t, err)
	}

	containerCfg := container.Config{
		Env: []string{
			"MARIADB_DATABASE=defaultdb",
			"MARIADB_ROOT_PASSWORD=secret",
		},
		ExposedPorts: nat.PortSet{
			nat.Port("3306/tcp"): {},
		},
		Image: mariaDBImage,
	}

	hostCfg := container.HostConfig{
		AutoRemove:      true,
		PublishAllPorts: true,
		Tmpfs:           map[string]string{"/var/lib/mysql": ""},
	}

	name := "mariadb-" + ulid.Make().String()

	cont, err := dockerClient.ContainerCreate(context.Background(), &containerCfg, &hostCfg, nil, nil, name)
	require.NoError(t, err, "failed to create mariadb docker container")

	t.Cleanup(func() {
		t.Logf("stopping container %s", name)
		timeoutSec := 5

		err := dockerClient.ContainerStop(context.Background(), cont.ID, container.StopOptions{Timeout: &timeoutSec})
		if err != nil && !errdefs.IsNotFound(err) {
			t.Logf("failed to stop mariadb container: %v", err)
		}
		t.Logf("stopped container %s", name)
	})

	err = dockerClient.ContainerStart(context.Background(), cont.ID, container.StartOptions{})
	require.NoError(t, err, "failed to start mariadb container")

	containerJSON, err := dockerClient.ContainerInspect(context.Background(), cont.ID)
	require.NoError(t, err)

	p, ok := containerJSON.NetworkSettings.Ports["3306/tcp"]
	if !ok || len(p) == 0 {
		require.Fail(t, "failed to get host port mapping from mariadb container")
	}

	mariaDBTestContainer := &mariaDBTestContainer{
		addr:     "localhost:" + p[0].HostPort,
		username: "root",
		password: "secret",
	}

	uri := mariaDBTestContainer.username + ":" + mariaDBTestContainer.password + "@tcp(" + mariaDBTestContainer.addr + ")/defaultdb?parseTime=true"

	err = mysql.SetLogger(log.New(io.Discard, "", 0))
	require.NoError(t, err)

	goose.SetLogger(goose.NopLogger())

	db, err := goose.OpenDBWithDriver("mysql", uri)
	require.NoError(t, err)
	t.Cleanup(func() {
		_ = db.Close()
	})

	backoffPolicy := backoff.NewExponentialBackOff()
	backoffPolicy.MaxElapsedTime = 2 * time.Minute
	err = backoff.Retry(
		func() error {
			return db.Ping()
		},
		backoffPolicy,
	)
	require.NoError(t, err, "failed to connect to mariadb container")

	goose.SetBaseFS(assets.EmbedMigrations)

	err = goose.Up(db, assets.MariaDBMigrationDir)
	require.NoError(t, err)
	version, err := goose.GetDBVersion(db)
	require.NoError(t, err)
	mariaDBTestContainer.version = version

	return mariaDBTestContainer
}

// GetConnectionURI returns the MariaDB connection uri for the running test container.
func (m *mariaDBTestContainer) GetConnectionURI(includeCredentials bool) string {
	creds := ""
	if includeCredentials {
		creds = m.username + ":" + m.password + "@"
	}

	return creds + "tcp(" + m.addr + ")/defaultdb?parseTime=true"
}

func (m *mariaDBTestContainer) GetUsername() string {
	return m.username
}

func (m *mariaDBTestContainer) GetPassword() string {
	return m.password
}

func (m *mariaDBTestContainer) CreateSecondary(t testing.TB) error {
	return nil
}

func (m *mariaDBTestContainer) GetSecondaryConnectionURI(includeCredentials bool) string {
	return ""
}
